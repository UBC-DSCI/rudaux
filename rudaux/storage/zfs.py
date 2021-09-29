from .storage import Storage
import paramiko as pmk
from scp import SCPClient
import pendulum as plm
import re
from traitlets import TraitType, Unicode, Dict, Callable
from .utilities import get_logger
from .utilities.traits import SSHAddress
import os
import tempfile
import subprocess

class ZFS(Storage):

    zfs_path = Unicode("/usr/sbin/zfs",
                        help="The path to the zfs executable").tag(config=True)
    tz = Unicode("UTC",
                        help="The timezone that the storage machine uses to unix timestamp its files").tag(config=True)

    unix = Dict(default_value={'user' : 'jupyter', 'group' : 'users'},
                        help="The dict of unix permissions for files written to storage: must specify unix.user and unix.group").tag(config=True)

    def __init__(self):
        self.open()

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def _command(self, cmd, status_fail=True):
        raise NotImplementedError

    def get_snapshots(self, volume):
        # send the list snapshot command
        stdout, stderr = self._command(f"{self.zfs_path} list -r -t snapshot -o name,creation {volume}")
        # parse the unique snapshot names
        snaps = self._parse_zfs_snaps(stdout)
        logger = get_logger()
        logger.info(f"Found {len(snaps)} ZFS snapshots")
        return snaps

    def _parse_zfs_snaps(self, stdout):
        # Example output from zfs snap list:
        #NAME                  CREATION
        #tank/home@now         Wed Jun 30 16:16 2010
        #tank/home/ahrens@now  Wed Jun 30 16:16 2010
        #tank/home/anne@now    Wed Jun 30 16:16 2010
        snaps = []
        for line in stdout:
            if '@' in line:
                volume, remaining = line.split('@', 1)
                name, remaining = remaining.split(' ', 1)
                datetime = plm.from_format(remaining.strip(), 'ddd MMM D H:mm YYYY')
                snaps.append( {'volume' : volume, 'name' : name, 'datetime':datetime} )
        return snaps

    def take_snapshot(self, volume, snapshot):
        volume = volume.strip("/")
        # execute the snapshot
        cmd = f"{self.zfs_path} snapshot -r {volume}@{snapshot}"
        stdout, stderr = self._command(cmd)

        # verify the snapshot
        snaps = self.get_snapshots()
        if f"{volume}@{snapshot}" not in [f"{snap['volume']}@{snap['name']}" for snap in snaps]:
            sig = signals.FAIL(f"Failed to take snapshot {snapshot}. Existing snaps: {snaps}")
            raise sig

    def create_volume(self, volume, quota):
        cmd = f"{self.zfs_path} create -o refquota={quota} {volume.strip('/')}"
        stdout, stderr = self._command(cmd)

    def read(self, volume, relative_path, snapshot=None):
        if snapshot:
            remote_path = os.path.join("/", volume.strip("/"), f".zfs/snapshot/{snapshot}", relative_path)
        else:
            remote_path = os.path.join("/", volume.strip("/"), relative_path)

        # create a temporary file
        tnf = tempfile.NamedTemporaryFile()
        # scp get to the tmp filename, preserve modified/created dates
        self.scp.get(remote_path, tnf.name, preserve_times=True)
        # get the unix timestamp of modification
        modified_datetime = plm.from_timestamp(os.path.getmtime(tnf.name), tz=self.tz)
        # get the file contents
        f = open(tnf.name, 'r')
        lines = f.readlines()
        f.close()
        # delete the temp file
        tnf.close()
        # return the data
        return lines, modified_datetime

    def write(self, lines, volume, relative_path):
        remote_volume_root = os.path.join("/", volume.strip("/"))
        remote_path = os.path.join(remote_volume_root, relative_path)
        remote_dir = os.path.dirname(remote_path)
        # make directories required to put the file if needed
        self._command('mkdir -p {remote_dir}')
        # save the lines to a temporary file
        tnf = tempfile.NamedTemporaryFile()
        f = open(tnf.name, 'w')
        f.writelines(lines)
        f.close()
        # put the file
        self.scp(tnf.name, recursive = False, remote_path = remote_path)
        # delete the temp file
        tnf.close()
        # change ownership of the volume to unix_user, unix_group
        self._command(f"chown -R {unix['user']} {remote_volume_root}")
        self._command(f"chgrp -R {unix['group']} {remote_volume_root}")
        # check if the file was written
        stdout, stderr = self._command(f"ls {remote_path}", status_fail=False)
        if "No such file" in stdout:
            sig = signals.FAIL(f"Failed to write file to storage: {remote_path}")
            raise sig 

class LocalZFS(ZFS):

    def open(self):
        pass

    def close(self):
        pass

    def _command(self, cmd, status_fail=True):
        logger = get_logger()
        logger.info(f"Running command {cmd}")

        pipes = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std_out, std_err = pipes.communicate()

        logger.info(f"Command exit code: {pipes.returncode}")

        if status_fail and pipes.returncode != 0:
            sig = signals.FAIL(f"Command error: nonzero exit status.\nstderr\n{stderr.decode('UTF-8')}\nstdout\n{stdout.decode('UTF-8')}")
            raise sig

        return stdout.decode('UTF-8'), stderr.decode('UTF-8')

class RemoteZFS(ZFS):

    ssh = Dict(default_value={'host': '127.0.0.1', 'port' : 22, 'user' : 'root'},
                        help="The dict of SSH connection information: must specify ssh.host, ssh.port, ssh.user").tag(config=True)

    def open(self):
        logger = get_logger()
        logger.info(f"Opening ssh connection to {ssh_info}")
        # open a ssh connection to the student machine
        ssh = pmk.client.SSHClient()
        ssh.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
        ssh.load_system_host_keys()
        ssh.connect(ssh_info['host'], ssh_info['port'], ssh_info['user'], allow_agent=True)
        s = ssh.get_transport().open_session()
        pmk.agent.AgentRequestHandler(s)
        self.ssh = ssh
        self.scp = SCPClient(ssh.get_transport())

    def close(self):
        self.ssh.close()

    def _command(self, cmd, status_fail=True):
        logger = get_logger()
        logger.info(f"Running ssh command {cmd}")
        # execute the snapshot command
        stdin, stdout, stderr = self.ssh.exec_command(cmd)

        # block on result
        out_status = stdout.channel.recv_exit_status()
        err_status = stderr.channel.recv_exit_status()

        logger.info(f"Command exit codes: out = {out_status}  err = {err_status}")

        # get output
        stdout_lines = ''
        for line in stdout:
            stdout_lines += line + '\n'
        stdout = stdout_lines

        stderr_lines = ''
        for line in stderr:
            stderr_lines += line + '\n'
        stderr = stderr_lines

        if status_fail and (out_status != 0 or err_status != 0):
            sig = signals.FAIL(f"Paramiko SSH command error: nonzero exit status.\nstderr\n{stderr}\nstdout\n{stdout}")
            raise sig

        # return
        return stdout, stderr

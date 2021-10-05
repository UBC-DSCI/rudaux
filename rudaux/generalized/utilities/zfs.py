import paramiko as pmk
from scp import SCPClient
import pendulum as plm
import re
from .utilities import get_logger
import os
import tempfile
import subprocess

class ZFS:
    def __init__(self, zfs_path = "/usr/sbin/zfs", tz = "UTC", info = None):
        self.zfs_path = zfs_path
        self.tz = tz
        self.info = info
        self.open()

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def _command(self, cmd, status_fail=True):
        raise NotImplementedError

    def _read(self, source_path, dest_path, preserve_times=True):
        raise NotImplementedError

    def _write(self, source_path, dest_path):
        raise NotImplementedError

    def get_snapshots(self, volume):
        # send the list snapshot command
        stdout, stderr = self._command(f"sudo {self.zfs_path} list -r -t snapshot -o name,creation {volume}")
        # parse the unique snapshot names
        snaps = self._parse_zfs_snaps(stdout)
        logger = get_logger()
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
        cmd = f"sudo {self.zfs_path} snapshot -r {volume}@{snapshot}"
        stdout, stderr = self._command(cmd)

        # verify the snapshot
        snaps = self.get_snapshots()
        if f"{volume}@{snapshot}" not in [f"{snap['volume']}@{snap['name']}" for snap in snaps]:
            raise Exception(f"Failed to take snapshot {snapshot}. Existing snaps: {snaps}")

    def create_volume(self, volume, quota, user, group):
        cmd = f"sudo {self.zfs_path} create -o refquota={quota} {volume.strip('/')}"
        stdout, stderr = self._command(cmd)

        # check if the volume was created & mounted
        stdout, stderr = self._command(f"sudo ls {os.path.join('/', volume.strip('/'))}", status_fail=False)
        if "No such file" in stdout:
            raise Exception(f"Failed to create volume: {volume}")

        # change ownership of the new volume
        path = os.path.join('/', volume.strip('/'))
        self._command(f"sudo chown -R {user} {path}")
        self._command(f"sudo chgrp -R {group} {path}")

    def read(self, volume, relative_path, snapshot=None):
        if snapshot:
            read_path = os.path.join("/", volume.strip("/"), f".zfs/snapshot/{snapshot}", relative_path)
        else:
            read_path = os.path.join("/", volume.strip("/"), relative_path)

        # create a temporary file
        tnf = tempfile.NamedTemporaryFile()
        # copy to the tmp filename, preserve modified/created dates
        self._read(read_path, tnf.name, preserve_times=True)
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
        # get volume root
        write_volume_root = os.path.join("/", volume.strip("/"))
        # get user + group for the volume
        stdout, stderr = self._command(f"sudo ls -ld {write_volume_root}", status_fail = False)
        if "No such file" in stdout:
            raise Exception(f"Cannot write to {volume}, no such directory at {write_volume_root}")
        line = stdout.split('\n')[0].split(' ')
        user = line[2]
        group = line[3]
        # get the write path for the file
        write_path = os.path.join(write_volume_root, relative_path)
        write_dir = os.path.dirname(write_path)
        # make directories required to put the file if needed
        self._command('sudo mkdir -p {write_dir}')
        # change ownership of the volume to unix_user, unix_group
        self._command(f"sudo chown -R {user} {write_volume_root}")
        self._command(f"sudo chgrp -R {group} {write_volume_root}")
        # save the lines to a temporary file
        tnf = tempfile.NamedTemporaryFile()
        f = open(tnf.name, 'w')
        f.writelines(lines)
        f.close()
        # write the file
        self._write(tnf.name, write_path)
        # delete the temp file
        tnf.close()
        # change ownership of the file to the correct user,group for the volume
        self._command(f"sudo chown {user} {write_path}")
        self._command(f"sudo chgrp {group} {write_path}")
        # check if the file was written
        stdout, stderr = self._command(f"sudo ls {write_path}", status_fail=False)
        if "No such file" in stdout:
            raise Exception(f"Failed to write file to storage: {write_path}")

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
            raise Exception(f"Command error: nonzero exit status.\nstderr\n{stderr.decode('UTF-8')}\nstdout\n{stdout.decode('UTF-8')}")

        return stdout.decode('UTF-8'), stderr.decode('UTF-8')

    def _copy(self, source_path, dest_path, preserve_times=False):
        logger = get_logger()
        logger.info(f"Copying file from {source_path} to {dest_path}")
        if preserve_times:
            self._command(f"cp -p {source_path} {dest_path}")
        else:
            self._command(f"cp {source_path} {dest_path}")

    def _write(self, source_path, dest_path):
        self._copy(source_path, dest_path)

    def _read(self, source_path, dest_path, preserve_times=True):
        self._copy(source_path, dest_path, preserve_times)

class RemoteZFS(ZFS):

    def open(self):
        logger = get_logger()
        logger.info(f"Opening ssh connection to {ssh_info}")
        # open a ssh connection to the student machine
        ssh = pmk.client.SSHClient()
        ssh.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
        ssh.load_system_host_keys()
        ssh.connect(self.info['host'], self.info['port'], self.info['user'], allow_agent=True)
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
            raise Exception(f"Paramiko SSH command error: nonzero exit status.\nstderr\n{stderr}\nstdout\n{stdout}")

        # return
        return stdout, stderr

    def _read(self, source_path, dest_path, preserve_times=True):
        self.scp.get(source_path, dest_path, preserve_times = preserve_times)

    def _write(self, source_path, dest_path):
        self.scp.put(source_path, recursive = False, remote_path = dest_path)



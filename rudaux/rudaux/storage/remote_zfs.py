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

class RemoteZFS(Storage):

    ssh = Dict(default_value={'host': '127.0.0.1', 'port' : 22, 'user' : 'root'}, help="The dict of SSH connection information: must specify ssh.host, ssh.port, ssh.user").tag(config=True)
    zfs_path = Unicode("/usr/sbin/zfs",
                        help="The path to the zfs executable").tag(config=True)
    tank_volume = Unicode("tank/home/dsci100",
                        help="The ZFS volume where student folders are stored").tag(config=True)
    get_student_folder = Callable(lambda stu : os.path.join("/tank/home/dsci100/", stu['id']),
                        help="A function that takes a student object and returns their work folder").tag(config=True)
    get_collectable_paths = Callable(lambda asgn : [f"{asgn['name']}/{asgn['name']}.ipynb"],
                        help="A function that takes a student object and assignment object and returns a list of remote paths to collect").tag(config=True)
    tz = Unicode("UTC",
                        help="The timezone that the storage machine uses to unix timestamp its files").tag(config=True)
    unix = Dict(default_value={'user' : 'jupyter', 'group' : 'users'},
                            help="The dict of unix permissions for files written to storage: must specify unix.user and unix.group").tag(config=True)

    def __init__(self):
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

    def get_snapshots(self):
        # send the list snapshot command
        stdout, stderr = self._command(f"{self.zfs_path} list -r -t snapshot -o name,creation {tank_volume}")
        # parse the unique snapshot names
        snaps = self._parse_zfs_snaps(stdout)
        logger = get_logger()
        logger.info(f"Found {len(snaps)} ZFS snapshots")
        return snaps

    def take_snapshot(self, snapshot, student=None, assignment=None):
        # execute the snapshot
        # if no specific student, snap the whole volume
        if student is None:
            cmd = f"{zfs_path} snapshot -r {tank_volume}@{snapshot}"
        else:
            cmd = f"{zfs_path} snapshot -r {self.get_student_folder(student).strip('/')}@{snapshot}"

        stdout, stderr = self._command(cmd)

        # verify the snapshot
        snaps = self.get_snapshots()
        if snap_path not in [f"{snap['volume']}@{snap['name']}" for snap in snaps]:
            sig = signals.FAIL(f"Failed to take snapshot {snap_name}. Existing snaps: {snaps}")
            raise sig

    def read(self, student, assignment, snapshot=None):
        base_path = self.get_student_folder(student)
        if snapshot:
            base_path = os.path.join(base_path, f".zfs/snapshot/{snapshot}")
        remote_relative_paths = self.get_collectable_paths(assignment)

        results = {}
        for rel in remote_relative_paths:
            # create a temporary randomized filename
            tmp_fn = next(tempfile._get_candidate_names())
            # construct the remote path
            remote_path = os.path.join(base_path, rel)
            # scp get to the tmp filename, preserve modified/created dates
            self.scp.get(remote_path, tmp_fn, preserve_times=True)
            # get the unix timestamp of modification
            modified_datetime = plm.from_timestamp(os.path.getmtime(tmp_fn), tz=self.storage_tz)
            # get the file contents
            tmp_f = open(tmp_fn, 'r')
            lines = tmp_f.readlines()
            tmp_f.close()
            # append to the results object
            results[rel] = {'data' : lines, 'datetime' : modified_datetime}
            # delete the temporary file
            os.remove(tmp_fn)

        return results

    def write(self, student, lines, remote_relative_path):
        remote_path = os.path.join(self.get_student_folder(student), remote_relative_path)
        # make directories required to put the file if needed
        #TODO
        # put the file
        # TODO
        # change ownership to unix_user, unix_group
        # TODO

        self.scp.put(local_relative_path, os.path.join(self.get_student_folder(student), remote_relative_path))
        stdout, stderr = self._command(f"ls {os.path.join(self.get_student_folder(student), remote_relative_path)}", status_fail=False)
        if "No such file" in stdout:
            sig = signals.FAIL(f"Failed to write file to storage: {remote_relative_path}")
            raise sig

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
        stdout_lines = []
        for line in stdout:
            stdout_lines.append(line)
        stdout = stdout_lines

        stderr_lines = []
        for line in stderr:
            stderr_lines.append(line)
        stderr = stderr_lines

        if status_fail and (out_status != 0 or err_status != 0):
            sig = signals.FAIL(f"Paramiko SSH command error: nonzero exit status.\nstderr\n{stderr}\nstdout\n{stdout}")
            raise sig

        # return
        return stdout, stderr

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

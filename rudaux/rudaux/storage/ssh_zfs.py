from .storage import Storage
import paramiko as pmk
from scp import SCPClient
import pendulum as plm
import re
from traitlets import TraitType, Unicode, Callable
from .utilities import get_logger
from .utilities.traits import SSHAddress

class SSH_ZFS_Storage(Storage):

    ssh_info = SSHAddress()
    zfs_path = Unicode()
    tank_volume = Unicode()
    get_student_folder = Callable()
    local_uid = Unicode()

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
            stdout, stderr = self._command(f"{zfs_path} snapshot -r {tank_volume}@{snapshot}") 
        else:
            stdout, stderr = self._command(f"{zfs_path} snapshot -r {self.get_student_folder(student).strip('/')}@{snapshot}")

        # verify the snapshot
        snaps = self.get_snapshots()
        if snap_path not in [f"{snap['volume']}@{snap['name']}" for snap in snaps]:
            sig = signals.FAIL(f"Failed to take snapshot {snap_name}. Existing snaps: {snaps}")
            raise sig

    def read(self, snapshot, student, remote_relative_path, local_relative_path):
        remote_path = os.path.join(self.get_student_folder(student), '.zfs/snapshot/{snapshot}', remote_relative_path)
        
        return datetime
        raise NotImplementedError

    def write(self, student, local_relative_path, remote_relative_path):
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

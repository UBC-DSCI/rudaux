from sys import stderr, stdout
from typing import Tuple, List, Dict, AnyStr
import paramiko as pmk
from pendulum import DateTime
from scp import SCPClient
import pendulum as plm
import re
from prefect import get_run_logger
# from logging import getLogger as get_run_logger
import os
import tempfile
import subprocess


# ====================================================================================================================
#                                                       ZFS
# ====================================================================================================================

def _parse_zfs_snaps(std_out: stdout) -> List[Dict]:
    # Example output from zfs snap list:
    # NAME                  CREATION
    # tank/home@now         Wed Jun 30 16:16 2010
    # tank/home/ahrens@now  Wed Jun 30 16:16 2010
    # tank/home/anne@now    Wed Jun 30 16:16 2010
    datetime_formats = [
        'ddd MMM DD HH:mm YYYY',
        'ddd MMM DD  H:mm YYYY',
        'ddd MMM  D HH:mm YYYY',
        'ddd MMM  D  H:mm YYYY'
    ]
    snaps = []
    creation_date_location = None
    for line in std_out.splitlines():
        if 'CREATION' in line:
            creation_date_location = line.find('CREATION')
        if '@' in line:
            name = line[:creation_date_location].strip()
            creation = line[creation_date_location:].strip()

            volume, snap_name = name.split('@', 1)
            datetime = None
            for datetime_format in datetime_formats:
                try:
                    datetime = plm.from_format(creation, datetime_format)
                    break
                except ValueError:
                    continue
            snaps.append({'volume': volume, 'name': snap_name, 'datetime': datetime})
    return snaps


class ZFS:
    # ----------------------------------------------------------------------------------------------------------------
    def __init__(self, zfs_path="/usr/sbin/zfs", tz="UTC", info=None):
        self.zfs_path = zfs_path
        self.tz = tz
        self.info = info
        self.open()

    # ----------------------------------------------------------------------------------------------------------------
    def open(self):
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------------------------
    def close(self):
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------------------------
    def _command(self, cmd: str, status_fail=True):
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------------------------
    def _read(self, source_path: str, dest_path: str, preserve_times=True):
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------------------------
    def _write(self, source_path: str, dest_path: str):
        raise NotImplementedError

    # ----------------------------------------------------------------------------------------------------------------
    def get_snapshots(self, volume: str) -> List[Dict]:
        # send the list snapshot command
        std_out, std_err = self._command(f"sudo {self.zfs_path} list -r -t snapshot -o name,creation {volume}")
        # parse the unique snapshot names
        snaps = _parse_zfs_snaps(std_out)
        logger = get_run_logger()
        return snaps

    # ----------------------------------------------------------------------------------------------------------------
    def take_snapshot(self, volume: str, snapshot: str):
        """
        takes a snapshot of volume

        Parameters
        ----------
        volume: str
        snapshot: str

        """
        volume = volume.strip("/")
        # execute the snapshot
        cmd = f"""sudo {self.zfs_path} snapshot -r "{volume}@{snapshot}" """
        std_out, std_err = self._command(cmd)

        # verify the snapshot
        snaps = self.get_snapshots(volume)
        if f"{volume}@{snapshot}" not in [f"{snap['volume']}@{snap['name']}" for snap in snaps]:
            raise Exception(f"Failed to take snapshot {snapshot}. Existing snaps: {snaps}")

    # ----------------------------------------------------------------------------------------------------------------
    def create_volume(self, volume: str, quota: str, user: str, group: str):
        """
        creates a volume

        Parameters
        ----------
        volume: str
        quota: str
            in the form: [size][G, M, K] (e.g., 10G)
        user: str
        group: str

        """
        cmd = f"sudo {self.zfs_path} create -o refquota={quota} {volume.strip('/')}"
        std_out, std_err = self._command(cmd)

        # check if the volume was created & mounted
        std_out, std_err = self._command(f"sudo ls {os.path.join('/', volume.strip('/'))}", status_fail=False)
        if "No such file" in stdout:
            raise Exception(f"Failed to create volume: {volume}")

        # change ownership of the new volume
        path = os.path.join('/', volume.strip('/'))
        self._command(f"sudo chown -R {user} {path}")
        self._command(f"sudo chgrp -R {group} {path}")

    # ----------------------------------------------------------------------------------------------------------------
    def read(self, volume: str, relative_path: str, snapshot=None) -> Tuple[List[AnyStr], DateTime]:
        """
        reads volume

        Parameters
        ----------
        volume: str
        relative_path: str
        snapshot:

        Returns
        -------
        (lines, modified_datetime): Tuple[List[AnyStr], DateTime]

        """
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

    # ----------------------------------------------------------------------------------------------------------------
    def write(self, lines: List[AnyStr], volume: str, relative_path: str):

        # get volume root
        write_volume_root = os.path.join("/", volume.strip("/"))

        # get user + group for the volume
        std_out, std_err = self._command(f"sudo ls -ld {write_volume_root}", status_fail=False)
        if "No such file" in std_out:
            raise Exception(f"Cannot write to {volume}, no such directory at {write_volume_root}")
        line = std_out.split('\n')[0].split(' ')
        user = line[2]
        group = line[3]

        # get the `write path` for the file
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
        std_out, std_err = self._command(f"sudo ls {write_path}", status_fail=False)
        if "No such file" in stdout:
            raise Exception(f"Failed to write file to storage: {write_path}")


# ====================================================================================================================
#                                                       LocalZFS
# ====================================================================================================================

class LocalZFS(ZFS):
    # ----------------------------------------------------------------------------------------------------------------
    def open(self):
        pass

    # ----------------------------------------------------------------------------------------------------------------
    def close(self):
        pass

    # ----------------------------------------------------------------------------------------------------------------
    def _command(self, cmd: str, status_fail=True) -> Tuple[str, str]:
        """
        runs the given command and outputs (std_out, std_err)

        Parameters
        ----------
        cmd: str
            the command to run
        status_fail: bool, defaults to True

        Returns
        -------
        (std_out, std_err): Tuple[stdout, stderr]
        """

        logger = get_run_logger()
        logger.info(f"Running command {cmd}")

        pipes = subprocess.Popen(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        std_out, std_err = pipes.communicate()

        logger.info(f"Command exit code: {pipes.returncode}")

        if status_fail and pipes.returncode != 0:
            raise Exception(
                f"Command error: nonzero exit status.\nstderr\n"
                f"{std_err.decode('UTF-8')}\nstdout\n{std_out.decode('UTF-8')}")

        return std_out.decode('UTF-8'), std_err.decode('UTF-8')

    # ----------------------------------------------------------------------------------------------------------------
    def _copy(self, source_path: str, dest_path: str, preserve_times=False):
        """
        copies file from source_path to dest_path

        Parameters
        ----------
        source_path: str
        dest_path: str
        preserve_times: bool, defaults to False
        """

        logger = get_run_logger()
        logger.info(f"Copying file from {source_path} to {dest_path}")
        if preserve_times:
            self._command(f"cp -p {source_path} {dest_path}")
        else:
            self._command(f"cp {source_path} {dest_path}")

    # ----------------------------------------------------------------------------------------------------------------
    def _write(self, source_path: str, dest_path: str):
        self._copy(source_path, dest_path)

    # ----------------------------------------------------------------------------------------------------------------
    def _read(self, source_path, dest_path, preserve_times=True):
        self._copy(source_path, dest_path, preserve_times)


# ====================================================================================================================
#                                                    RemoteZFS
# ====================================================================================================================

class RemoteZFS(ZFS):
    # ----------------------------------------------------------------------------------------------------------------
    def __init__(self, zfs_path="/usr/sbin/zfs", tz="UTC", info=None):
        self.scp = None
        self.ssh = None
        super().__init__(zfs_path, tz, info)

    # ----------------------------------------------------------------------------------------------------------------
    def open(self):
        logger = get_run_logger()
        logger.info(f"Opening ssh connection to {self.info}")
        # open an ssh connection to the student machine
        self.ssh = pmk.client.SSHClient()
        self.ssh.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
        self.ssh.load_system_host_keys()
        self.ssh.connect(self.info['host'], self.info['port'], self.info['user'], allow_agent=True)
        s = self.ssh.get_transport().open_session()
        pmk.agent.AgentRequestHandler(s)
        self.scp = SCPClient(self.ssh.get_transport())

    # ----------------------------------------------------------------------------------------------------------------
    def close(self):
        self.ssh.close()

    # ----------------------------------------------------------------------------------------------------------------
    def _command(self, cmd: str, status_fail=True) -> Tuple[str, str]:
        """
        runs the given command and outputs (std_out, std_err)

        Parameters
        ----------
        cmd: str
            the command to run
        status_fail: bool, defaults to True

        Returns
        -------
        (std_out, std_err): Tuple[stdout, stderr]
        """

        logger = get_run_logger()
        logger.info(f"Running ssh command {cmd}")
        # execute the snapshot command
        std_in, std_out, std_err = self.ssh.exec_command(cmd)

        # block on result
        out_status = std_out.channel.recv_exit_status()
        err_status = std_err.channel.recv_exit_status()

        logger.info(f"Command exit codes: out = {out_status}  err = {err_status}")

        # get output
        stdout_lines = ''
        for line in std_out:
            stdout_lines += line + '\n'
        std_out = stdout_lines

        stderr_lines = ''
        for line in std_err:
            stderr_lines += line + '\n'
        std_err = stderr_lines

        if status_fail and (out_status != 0 or err_status != 0):
            raise Exception(f"Paramiko SSH command error: nonzero exit status.\nstderr\n{std_err}\nstdout\n{std_out}")

        # return
        return std_out, std_err

    # ----------------------------------------------------------------------------------------------------------------
    def _read(self, source_path: str, dest_path: str, preserve_times=True):
        self.scp.get(source_path, dest_path, preserve_times=preserve_times)

    # ----------------------------------------------------------------------------------------------------------------
    def _write(self, source_path: str, dest_path: str):
        self.scp.put(source_path, recursive=False, remote_path=dest_path)

    # ----------------------------------------------------------------------------------------------------------------

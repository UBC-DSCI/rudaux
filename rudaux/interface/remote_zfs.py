import os

from rudaux.util.ssh import SSHUtil
from rudaux.interface.base.submission_system import SubmissionSystem
from rudaux.model import Assignment, Student
from rudaux.model.document import Document
from rudaux.model.snapshot import parse_snapshot_from_name, Snapshot
from rudaux.util.zfs import RemoteZFS

from loguru import logger

from pydantic import PrivateAttr
from typing import Dict, List, Any

class RemoteZFSSubmissions(SubmissionSystem):
    ssh_config: Dict[str, dict]
    student_local_assignment_folder: str
    _super_ssh_client: PrivateAttr(default=None)
    _ssh_client: PrivateAttr(default=None)


    def open(self, course_section_name: str):
        self._super_ssh_client = SSHUtil().ssh_open(self.ssh_config, course_section_name, superuser=True)
        self._ssh_client = SSHUtil().ssh_open(self.ssh_config, course_section_name, superuser=False)

    def close(self):
        pass

    def list_snapshots(self, course_section_name: str, assignments: Dict[str, Assignment], students: Dict[str, Student]) -> List[Snapshot]:
        client = self._ssh_client
        remotezfs = RemoteZFS(client=client, tz=self.ssh_config[course_section_name]['timezone'])
        snap_dicts = remotezfs.get_snapshots(self.ssh_config[course_section_name]['student_root'])

        snapshots = []
        for snap_dict in snap_dicts:
            snapshot = parse_snapshot_from_name(snap_dict["name"], assignments, students, snap_dict["volume"])
            if snapshot is not None:
                snapshots.append(snapshot)

        return snapshots

        
    
    def take_snapshot(self, course_section_name: str, snapshot: Snapshot):
        client = self._super_ssh_client
        remotezfs = RemoteZFS(client=client, tz=self.ssh_config[course_section_name]['timezone'])
        try:
            remotezfs.take_snapshot(self.ssh_config[course_section_name]['student_root'], snapshot.get_name())
        except Exception as e:
            if "dataset already exists" in str(e).lower():
                logger.info(f"Snapshot {snapshot.get_name()} already exists.")
            else:
                raise e

    
    def collect_snapshot(self, course_section_name: str, snapshot: Snapshot):
        client = self._ssh_client
        remotezfs = RemoteZFS(client=client, tz=self.ssh_config[course_section_name]['timezone'])
        volume = self.ssh_config[course_section_name]['student_root']   
        file_extension = '.ipynb'
        relpath = os.path.join(snapshot.student.lms_id, f'.zfs/snapshot/{snapshot.get_name()}', self.student_local_assignment_folder, snapshot.assignment.name, snapshot.assignment.name + file_extension)
        data, meta = remotezfs.read(volume, relpath)
        
        return Document(info=meta, data=data)

    
    def distribute(self, course_section_name: str, student: Student, document, filename: str, dirpath:str):
        client = self._ssh_client
        remotezfs = RemoteZFS(client=client, tz=self.ssh_config[course_section_name]['timezone'])
        volume = self.ssh_config[course_section_name]['student_root']   
        relpath = os.path.join(student.lms_id, dirpath, filename)

        remotezfs.write(document.data, volume, relpath)

    
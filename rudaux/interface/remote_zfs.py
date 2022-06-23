from typing import Dict, List
from .submission_system import SubmissionSystem

class RemoteZFS(SubmissionSystem):
    
    def open(self):
        pass

    def close(self):
        pass

    def get_snapshots(self):
        pass

    def take_snapshot(self, snapshot, student=None, assignment=None):
        pass

    def read(self, student, storage_relative_path, local_relative_path, snapshot=None):
        pass

    def write(self, student, local_relative_path, storage_relative_path):
        pass

from pydantic import BaseModel
from abc import ABC, abstractmethod


class SubmissionSystem(ABC, BaseModel):

    @abstractmethod
    def open(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_snapshots(self):
        pass

    @abstractmethod
    def take_snapshot(self, snapshot, student=None, assignment=None):
        pass

    @abstractmethod
    def read(self, student, storage_relative_path, local_relative_path, snapshot=None):
        pass

    @abstractmethod
    def write(self, student, local_relative_path, storage_relative_path):
        pass

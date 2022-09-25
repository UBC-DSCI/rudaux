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
    def list_snapshots(self, assignments, students):
        pass

    @abstractmethod
    def take_snapshot(self, snapshot):
        pass

    @abstractmethod
    def collect_snapshot(self, snapshot):
        pass

    @abstractmethod
    def distribute(self, student, document_info, document_data):
        pass

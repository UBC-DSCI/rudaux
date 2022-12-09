from enum import IntEnum
from typing import Dict, List
from pydantic import BaseModel
from abc import ABC, abstractmethod
from rudaux.model import Assignment, Student
from rudaux.model.snapshot import Snapshot


class SubmissionGradingStatus(IntEnum):
    NOT_ASSIGNED = 11
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    AUTOGRADED = 6
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10


class SubmissionSystem(ABC, BaseModel):
    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def open(self, course_name: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def close(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def list_snapshots(self, course_name: str, assignments: Dict[str, Assignment],
                       students: Dict[str, Student]) -> List[Snapshot]:
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def take_snapshot(self, course_name: str, snapshot: Snapshot):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def collect_snapshot(self, snapshot: Snapshot):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def distribute(self, student: Student, document):
        pass

    # -----------------------------------------------------------------------------------------

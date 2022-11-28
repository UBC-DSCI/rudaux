from enum import IntEnum
from typing import List

from pydantic import BaseModel
from abc import ABC, abstractmethod

from rudaux.model import Submission
from rudaux.model.grader import Grader


class GradingStatus(IntEnum):
    NOT_ASSIGNED = 11
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    AUTOGRADED = 6
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10


class GradingSystem(ABC, BaseModel):
    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def open(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def close(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def initialize(self):
        pass

    # -----------------------------------------------------------------------------------------
    def generate_assignment(self, grader: Grader):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def generate_solution(self, grader: Grader):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def generate_feedback(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def get_needs_manual_grading(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def autograde(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def build_grader(self, course_name: str, assignment_name: str, username: str, skip: bool) -> Grader:
        pass

    # -----------------------------------------------------------------------------------------
    # def get_users(self) -> List[str]:
    #     pass

    # -----------------------------------------------------------------------------------------
    # def add_grader_account(self, grader: Grader):
    #     pass

    # -----------------------------------------------------------------------------------------
    def initialize_grader(self, grader: Grader):
        pass

    # -----------------------------------------------------------------------------------------
    def assign_submission_to_grader(self, graders: List[Grader], submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    def collect_grader_submissions(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    def clean_grader_submission(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    def return_feedback(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    def compute_grades(self, submission: Submission) -> str:
        pass

    # -----------------------------------------------------------------------------------------

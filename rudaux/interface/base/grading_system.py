from typing import List

from pydantic import BaseModel
from abc import ABC, abstractmethod

from rudaux.model import Submission
from rudaux.model.grader import Grader


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
    def get_generated_assignments(self, work_dir: str) -> dict:
        pass

    # -----------------------------------------------------------------------------------------
    def generate_assignment(self, assignment_name: str, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def generate_solution(self, local_source_path: str, solution_name: str, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def generate_feedback(self, submission: Submission, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def get_needs_manual_grading(self, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def autograde(self, submission: Submission, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def build_grader(self, course_name: str, assignment_name: str, username: str) -> Grader:
        pass

    # -----------------------------------------------------------------------------------------
    def get_users(self) -> List[str]:
        pass

    # -----------------------------------------------------------------------------------------
    def add_grader_account(self, grader: Grader):
        pass

    # -----------------------------------------------------------------------------------------

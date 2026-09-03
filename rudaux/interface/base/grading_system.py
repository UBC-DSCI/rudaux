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
    @abstractmethod
    def initialize_graders(self, graders: List[Grader]) -> List[Grader]:
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def assign_submission_to_grader(self, graders: List[Grader], submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def collect_grader_submissions(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def clean_grader_submission(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def return_solution(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def return_feedback(self, submission: Submission):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def compute_submission_percent_grade(self, submission: Submission) -> str:
        pass

    # -----------------------------------------------------------------------------------------

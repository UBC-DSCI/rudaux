from pydantic import BaseModel
from abc import ABC, abstractmethod

from rudaux.model import Submission


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

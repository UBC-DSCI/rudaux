from pydantic import BaseModel
from abc import ABC, abstractmethod


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
    def generate_solution(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def generate_feedback(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def get_needs_manual_grading(self):
        pass

    # -----------------------------------------------------------------------------------------
    @abstractmethod
    def autograde(self):
        pass

    # -----------------------------------------------------------------------------------------

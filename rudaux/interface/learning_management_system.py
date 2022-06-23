from pydantic import BaseModel
from abc import ABC, abstractmethod
from ..model import Student, Assignment, Override

class LearningManagementSystem(ABC,BaseModel):

    @abstractmethod
    def open(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_course_info(self):
        pass

    @abstractmethod
    def get_students(self):
        pass

    @abstractmethod
    def get_instructors(self):
        pass

    @abstractmethod
    def get_groups(self):
        pass

    @abstractmethod
    def get_assignments(self):
        pass 

    @abstractmethod
    def get_submissions(self, assignment):
        pass

    @abstractmethod
    def update_grade(self, submission):
        pass

    @abstractmethod
    def update_override(self, override):
        pass

from abc import ABC, abstractmethod
from pydantic import BaseModel
from .models import Student, Assignment, Override

class LMS(ABC, BaseModel):

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
    def get_submissions(self, assignment : Assignment):
        pass

    @abstractmethod
    def update_grade(self, submission : Submission):
        pass

    @abstractmethod
    def update_override(self, override : Override):
        pass

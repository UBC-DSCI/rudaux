from abc import ABC, abstractmethod
from .models import Student, Assignment, Override

class LMS(ABC):

    def __init__(self, api_info):
        self.api_info = api_info

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

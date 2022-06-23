from typing import Dict, List
from .learning_management_system import LearningManagementSystem

class Canvas(LearningManagementSystem):
    canvas_base_domain : str 
    canvas_course_lms_ids : Dict[str, str]
    canvas_registration_deadlines : Dict[str, str]
    canvas_api_tokens : Dict[str, str]

    def open(self):
        pass

    def close(self):
        pass

    def get_course_info(self):
        pass

    def get_students(self):
        pass

    def get_instructors(self):
        pass

    def get_groups(self):
        pass

    def get_assignments(self):
        pass 

    def get_submissions(self, assignment):
        pass

    def update_grade(self, submission):
        pass

    def update_override(self, override):
        pass



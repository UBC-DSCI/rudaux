import fwirl
import pendulum as plm
from fwirl.resource import Resource
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system


# ------------------------------------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------------------------------------
class LMSResource(Resource):
    def __init__(self, key, settings, course_name):
        super().__init__(key)
        self.course_name = course_name
        self.lms = get_learning_management_system(settings=settings, group_name=course_name)
        self.list_of_students = None
        self.list_of_assignments = None
        self.list_of_graders = None

    def init(self):
        pass

    def close(self):
        pass

    def get_course_section_info(self, course_section_name: str):
        course_section_info = get_course_section_info(
            lms=self.lms, course_section_name=course_section_name)
        return course_section_info

    def get_students(self, course_section_name: str):
        students = get_students(
            lms=self.lms, course_section_name=course_section_name)
        return students

    def get_assignments(self, course_section_name):
        assignments = get_assignments(
            lms=self.lms, course_group_name=self.course_name,
            course_section_name=course_section_name)
        return assignments


# ------------------------------------------------------------------------------------------------
class GradingSystemResource(Resource):
    def __init__(self, key):
        super().__init__(key)

    def init(self):
        pass

    def close(self):
        pass


# ------------------------------------------------------------------------------------------------
class SubmissionSystemResource(Resource):
    def __init__(self, key):
        super().__init__(key)

    def init(self):
        pass

    def close(self):
        pass

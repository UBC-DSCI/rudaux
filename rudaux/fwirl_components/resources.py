import fwirl
import pendulum as plm
from fwirl.resource import Resource
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system


# ------------------------------------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------------------------------------
class LMSResource(Resource):
    def __init__(self, key, settings, course_name, min_query_interval):
        super().__init__(key)
        self.course_name = course_name
        self.lms = get_learning_management_system(settings=settings, group_name=course_name)
        self.course_section_info = None
        self.list_of_students = None
        self.list_of_assignments = None
        self.list_of_graders = None
        self.last_request_time = None
        self.result_life_span = None
        self.results_timestamps = dict()
        self.min_query_interval = min_query_interval    # 10 s

    def init(self):
        pass

    def close(self):
        pass

    def get_course_section_info(self, course_section_name: str):
        if self.course_section_info is None \
                or (plm.now() - self.results_timestamps['course_section_info']) > self.result_life_span:
            self.results_timestamps['course_section_info'] = plm.now()
            self.course_section_info = self.lms.get_course_section_info(course_section_name=course_section_name)
        return self.course_section_info

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

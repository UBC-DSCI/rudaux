import fwirl
from fwirl.resource import Resource

import os
import pendulum as plm

from typing import List

from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system
from rudaux.model import Assignment, Submission, Override


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
        self.list_of_instructors = None
        self.list_of_tas = None
        self.list_of_assignments = None
        self.dict_of_submissions = None
        self.list_of_graders = None
        self.last_request_time = None
        self.result_life_span = plm.duration(minutes=15)
        self.results_timestamps = dict()
        self.min_query_interval = min_query_interval  # 10 s

    def init(self):
        pass

    def close(self):
        pass

    def get_course_section_info(self, course_section_name: str):
        if self.course_section_info is None \
                or (plm.now() - self.results_timestamps['course_section_info']) > self.result_life_span:
            self.results_timestamps['course_section_info'] = plm.now()
            self.course_section_info = self.lms.get_course_section_info(
                course_section_name=course_section_name
            )
        return self.course_section_info

    def get_students(self, course_section_name: str):
        if self.list_of_students is None \
                or (plm.now() - self.results_timestamps['list_of_students']) > self.result_life_span:
            self.results_timestamps['list_of_students'] = plm.now()
            self.list_of_students = self.lms.get_students(
                course_section_name=course_section_name
            )
        return self.list_of_students
    
    def get_instructors(self, course_section_name: str):
        if self.list_of_instructors is None \
                or (plm.now() - self.results_timestamps['list_of_instructors']) > self.result_life_span:
            self.results_timestamps['l ist_of_instructors'] = plm.now()
            self.list_of_instructors = self.lms.get_instructors(
                course_section_name=course_section_name
            )
        return self.list_of_instructors
    
    def get_tas(self, course_section_name: str):
        if self.list_of_tas is None \
                or (plm.now() - self.results_timestamps['list_of_tas']) > self.result_life_span:
            self.results_timestamps['l ist_of_tas'] = plm.now()
            self.list_of_instructors = self.lms.get_tas(
                course_section_name=course_section_name
            )
        return self.list_of_tas

    def get_assignments(self, course_section_name):
        if self.list_of_assignments is None \
                or (plm.now() - self.results_timestamps['list_of_assignments']) > self.result_life_span:
            self.results_timestamps['list_of_assignments'] = plm.now()
            self.list_of_assignments = self.lms.get_assignments(
                course_group_name=self.course_name,
                course_section_name=course_section_name
            )
        return self.list_of_assignments
    
    def get_submissions(self, course_section_name:str, assignment: Assignment):
        if self.dict_of_submissions is None or assignment.lms_id not in self.dict_of_submissions \
                or (plm.now() - self.results_timestamps[f'dict_of_submissions_{assignment.lms_id}']) > self.result_life_span:
            self.results_timestamps[f'dict_of_submissions_{assignment.lms_id}'] = plm.now()

            if self.dict_of_submissions is None:
                self.dict_of_submissions = {}

            self.dict_of_submissions[str(assignment.lms_id)] = self.lms.get_submissions(
                course_group_name=self.course_name,
                course_section_name=course_section_name,
                assignment=assignment
            )
        return self.dict_of_submissions[str(assignment.lms_id)]
    
    def update_grade(self, course_section_name:str, submission: Submission):
        self.lms.update_grade(course_section_name, submission)

    def update_override(self, course_section_name:str, override:Override):
        self.lms.update_override(course_section_name, override)

    def create_overrides(self, course_section_name:str, overrides:List[Override]):
        self.lms.create_overrides(course_section_name, overrides)

    def delete_overrides(self, course_section_name:str, overrides:List[Override]):
        self.lms.delete_overrides(course_section_name, overrides)

# ------------------------------------------------------------------------------------------------
class GradingSystemResource(Resource):
    def __init__(self, key, settings, course_name):
        super().__init__(key)
        self.course_name = course_name
        self.settings = settings
        self.gradsys = get_grading_system(settings=settings, group_name=course_name)

    def init(self):
        pass

    def close(self):
        pass

    def build_grader(self, course_name, assignment_name, username, skip):
        return self.gradsys.build_grader(course_name, assignment_name, username, skip)

    def initialize_graders(self, graders):
        self.gradsys.initialize_graders(graders)

    def assign_submission_to_grader(self, graders, submission):
        self.gradsys.assign_submission_to_grader(graders, submission)

    def collect_grader_submission(self, submission):
        self.gradsys.collect_grader_submission(submission)

    def clean_submission(self, submission):
        self.gradsys.clean_grader_submission(submission)

    def autograde_submission(self, submission):
        self.gradsys.autograde(submission)

    def generate_assignment(self, grader):
        self.gradsys.generate_assignment(grader)

    def check_manual_grading(self, submission):
        self.gradsys.get_needs_manual_grading(submission)
    
    def generate_feedback(self, submission):
        self.gradsys.generate_feedback(submission)

    def return_solution(self, submission):
        self.gradsys.return_solution(submission)

    def return_feedback(self, submission):
        self.gradsys.return_feedback(submission)

    def compute_submission_percent_grade(self, submission):
        self.gradsys.compute_submission_percent_grade(submission)

# ------------------------------------------------------------------------------------------------
class SubmissionSystemResource(Resource):
    def __init__(self, key, settings, course_name, course_section_name):
        super().__init__(key)
        self.course_name = course_name
        self.settings = settings
        self.subsys = get_submission_system(settings=settings, group_name=course_name)

        self.subsys.open(course_section_name)

    def init(self):
        pass

    def close(self):
        pass

    def list_snapshots(self, course_section_name, assignments, students):
        return self.subsys.list_snapshots(course_section_name, assignments, students)

    def take_snapshot(self, course_section_name, snapshot):
        self.subsys.take_snapshot(course_section_name, snapshot)

    def collect_snapshot(self, course_section_name, snapshot):
        return self.subsys.collect_snapshot(course_section_name, snapshot)

    def distribute(self, course_section_name, student, document, filename, dirpath=''):
        self.subsys.distribute(course_section_name, student, document, filename, dirpath)
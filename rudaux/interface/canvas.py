from typing import Dict, List

from pendulum import DateTime
from pendulum.tz.timezone import Timezone

from rudaux.interface.base.learning_management_system import LearningManagementSystem
from rudaux.util.canvasapi import get_course_info, get_people, get_groups, get_submissions, get_assignments
from rudaux.util.canvasapi import update_grade, _create_override, _remove_override
from rudaux.model.course_info import CourseInfo
from rudaux.model.assignment import Assignment
from rudaux.model.student import Student
from rudaux.model.instructor import Instructor
from rudaux.model.submission import Submission
from rudaux.model.override import Override


class Canvas(LearningManagementSystem):
    canvas_base_domain: str
    canvas_course_lms_ids: Dict[str, str]
    canvas_registration_deadlines: Dict[str, str]
    canvas_api_tokens: Dict[str, str]
    assignments: Dict[str, dict]

    # ---------------------------------------------------------------------------------------------------
    def open(self):
        pass

    # ---------------------------------------------------------------------------------------------------
    def close(self):
        pass

    # ---------------------------------------------------------------------------------------------------
    def get_course_info(self, course_section_name) -> CourseInfo:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        ci = get_course_info(api_info={canvas_id: api_info}, course_id=canvas_id)
        course_info = CourseInfo(lms_id=ci['lms_id'], name=ci['name'], code=ci['code'],
                                 start_at=ci['start_at'], end_at=ci['end_at'], time_zone=ci['time_zone'])
        return course_info

    # ---------------------------------------------------------------------------------------------------
    def get_students(self, course_section_name) -> List[Student]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        students = get_people(api_info={canvas_id: api_info}, course_id=canvas_id,
                              enrollment_type="StudentViewEnrollment")  # StudentEnrollment

        # print(students)

        students = [Student(
            lms_id=s['lms_id'], name=s['name'], sortable_name=s['sortable_name'],
            school_id=s['school_id'], reg_date=s['reg_date'], status=s['status']) for s in students]
        return students

    # ---------------------------------------------------------------------------------------------------
    def get_instructors(self, course_section_name: str) -> List[Instructor]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        instructors = get_people(api_info={canvas_id: api_info}, course_id=canvas_id,
                                 enrollment_type="TeacherEnrollment")

        instructors = [Instructor(
            lms_id=i['lms_id'], name=i['name'], sortable_name=i['sortable_name'],
            school_id=i['school_id'], reg_date=i['reg_date'], status=i['status']) for i in instructors]
        return instructors

    # ---------------------------------------------------------------------------------------------------
    def get_tas(self, course_section_name: str):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        return get_people(api_info={canvas_id: api_info}, course_id=canvas_id,
                          enrollment_type="TaEnrollment")  # look it up might be wrong

    # ---------------------------------------------------------------------------------------------------
    def get_groups(self, course_section_name: str):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        return get_groups(api_info={canvas_id: api_info}, course_id=canvas_id)

    # ---------------------------------------------------------------------------------------------------
    def get_assignments(self, course_group_name: str, course_section_name: str) -> List[Assignment]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        assignments_dict = get_assignments(api_info={canvas_id: api_info}, course_id=canvas_id,
                                           assignment_names=self.assignments[course_group_name])

        # print(assignments_dict)

        assignments = []
        for a in assignments_dict:
            overrides = []
            for o in a['overrides']:
                students = []
                for s in o['students']:
                    student = Student(
                        lms_id=s['lms_id'], name=s['name'], sortable_name=s['sortable_name'],
                        school_id=s['school_id'], reg_date=s['reg_date'], status=s['status'])
                    students.append(student)
                override = Override(
                    lms_id=o['lms_id'], name=o['name'], due_at=o['due_at'],
                    lock_at=o['lock_at'], unlock_at=o['unlock_at'], students=students)
                overrides.append(override)

            assignment = Assignment(
                lms_id=a['lms_id'], name=a['name'], due_at=a['due_at'],
                lock_at=a['lock_at'], unlock_at=a['unlock_at'], overrides=overrides,
                published=a['published']
            )
            assignments.append(assignment)

        return assignments

    # ---------------------------------------------------------------------------------------------------
    def get_submissions(self, course_group_name: str, course_section_name: str,
                        assignment: dict) -> List[Submission]:

        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        submissions_dict = get_submissions(api_info={canvas_id: api_info},
                                           course_id=canvas_id, assignment=assignment)

        # print(submissions_dict)

        all_students = self.get_students(course_section_name=course_section_name)
        all_assignments = self.get_assignments(course_group_name=course_group_name,
                                               course_section_name=course_section_name)

        submissions = []
        for assignment_obj in all_assignments:
            for student_obj in all_students:
                # fetch the pair from submissions_dict
                if assignment_obj.lms_id in submissions_dict:
                    if student_obj.lms_id in submissions_dict[assignment_obj.lms_id]:
                        submission = submissions_dict[assignment_obj.lms_id][student_obj.lms_id]

                        submission['score'] = 100
                        submission['posted_at'] = DateTime(2022, 9, 21, 17, 12, 10, tzinfo=Timezone('UTC'))
                        submission['excused'] = False

                        submission = Submission(
                            lms_id=canvas_id,
                            student=student_obj,
                            assignment=assignment_obj,
                            score=submission['score'],
                            posted_at=submission['posted_at'],
                            late=submission['late'],
                            missing=submission['missing'],
                            excused=submission['excused']
                        )
                        submissions.append(submission)

        return submissions

    # ---------------------------------------------------------------------------------------------------
    def update_grade(self, course_section_name: str, submission: Submission):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        return update_grade(api_info={canvas_id: api_info}, course_id=canvas_id, submission=submission,
                            assignment=submission.assignment.lms_id,
                            student=submission.student.lms_id, score=submission.score)

    # ---------------------------------------------------------------------------------------------------
    def update_override(self, course_name, override):
        pass

    # ---------------------------------------------------------------------------------------------------
    def create_overrides(self, course_section_name, assignment, override):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        return _create_override(api_info={canvas_id: api_info}, assignment=assignment, override=override)

    # ---------------------------------------------------------------------------------------------------
    def delete_overrides(self, course_section_name, assignment, override):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        return _remove_override(api_info={canvas_id: api_info}, assignment=assignment, override=override)

    # ---------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    from rudaux.model.settings import Settings
    from rudaux.flows import load_settings
    import importlib


    def get_class_from_string(s):
        module_name, class_name = s.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)


    def get_learning_management_system(settings, config_path, group_name):
        LMS = get_class_from_string(settings.lms_classes[group_name])
        if not issubclass(LMS, LearningManagementSystem):
            raise ValueError
        lms = LMS.parse_file(config_path)
        return lms


    _config_path = "/home/alireza/Desktop/SES/rudaux/rudaux_config.json"
    _group_name = "course_dsci_100_test"
    _course_name = "section_dsci_100_test_01"

    settings = load_settings(_config_path)
    settings = Settings.parse_obj(settings)
    lms = get_learning_management_system(settings, config_path=_config_path, group_name=_group_name)

    print(lms.get_course_info(course_section_name=_course_name))
    print(lms.get_students(course_section_name=_course_name))
    print(lms.get_instructors(course_section_name=_course_name))
    print(lms.get_groups(course_section_name=_course_name))
    print(lms.get_assignments(course_group_name=_group_name, course_section_name=_course_name))
    print(lms.get_submissions(course_group_name=_group_name, course_section_name=_course_name,
                              assignment={'id': '1292206', 'name': 'test_assignment'}))

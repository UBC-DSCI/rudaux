from typing import Dict, List

from pendulum import DateTime
import pendulum as plm
from pendulum.tz.timezone import Timezone

from rudaux.interface.base.learning_management_system import LearningManagementSystem
from rudaux.interface.base.submission_system import SubmissionGradingStatus
from rudaux.util.canvasapi import get_course_info, get_people, get_groups, get_submissions, get_assignments
from rudaux.util.canvasapi import update_grade, _create_override, _remove_override
from rudaux.model.course_section_info import CourseSectionInfo
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
    def get_course_section_info(self, course_section_name: str) -> CourseSectionInfo:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        ci = get_course_info(api_info={canvas_id: api_info}, course_id=canvas_id)
        course_section_info = CourseSectionInfo(
            lms_id=ci['lms_id'], name=ci['name'], code=ci['code'],
            start_at=ci['start_at'], end_at=ci['end_at'], time_zone=ci['time_zone']
        )
        return course_section_info

    # ---------------------------------------------------------------------------------------------------
    def get_students(self, course_section_name) -> Dict[str, Student]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        students = get_people(api_info={canvas_id: api_info}, course_id=canvas_id,
                              enrollment_type="StudentEnrollment")  # StudentEnrollment

        # print(students)

        students = {s['lms_id']: Student(
            lms_id=s['lms_id'], name=s['name'], sortable_name=s['sortable_name'],
            school_id=s['school_id'], reg_date=s['reg_date'], status=s['status']) for s in students
        }
        return students

    # ---------------------------------------------------------------------------------------------------
    def get_instructors(self, course_section_name: str) -> Dict[str, Instructor]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        instructors = get_people(api_info={canvas_id: api_info}, course_id=canvas_id,
                                 enrollment_type="TeacherEnrollment")

        instructors = {i['lms_id']: Instructor(
            lms_id=i['lms_id'], name=i['name'], sortable_name=i['sortable_name'],
            school_id=i['school_id'], reg_date=i['reg_date'], status=i['status']) for i in instructors
        }
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
    def get_assignments(self, course_group_name: str, course_section_name: str) -> Dict[str, Assignment]:
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        assignments_dict = get_assignments(api_info={canvas_id: api_info}, course_id=canvas_id,
                                           assignment_names=self.assignments[course_group_name])

        # print(assignments_dict)
        all_students = self.get_students(course_section_name=course_section_name)
        course_section_info = self.get_course_section_info(course_section_name=course_section_name)

        assignments = dict()
        for a in assignments_dict:
            overrides = dict()
            for o in a['overrides']:
                students = dict()
                if 'student_ids' in o:
                    for s_id in o['student_ids']:
                        student = all_students[s_id]
                        # student = Student(
                        #     lms_id=s['lms_id'], name=s['name'], sortable_name=s['sortable_name'],
                        #     school_id=s['school_id'], reg_date=s['reg_date'], status=s['status'])
                        students[student.lms_id] = student
                    override = Override(
                        lms_id=o['id'], name=o['title'], due_at=o['due_at'],
                        lock_at=o['lock_at'], unlock_at=o['unlock_at'],
                        students=students, course_section_info=course_section_info)

                    overrides[override.lms_id] = override

            skip = a['due_at'] > plm.now()

            assignment = Assignment(
                lms_id=a['id'], name=a['name'], due_at=a['due_at'],
                lock_at=a['lock_at'], unlock_at=a['unlock_at'], overrides=overrides,
                published=a['published'], course_section_info=course_section_info,
                skip=skip
            )
            assignments[assignment.lms_id] = assignment

        return assignments

    # ---------------------------------------------------------------------------------------------------
    def get_submissions(self, course_group_name: str, course_section_name: str,
                        assignment: Assignment) -> List[Submission]:

        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        submissions_dict = get_submissions(
            api_info={canvas_id: api_info}, course_id=canvas_id,
            assignment={
                'id': assignment.lms_id,
                'name': assignment.name
            }
        )

        # print(submissions_dict)

        all_students = self.get_students(course_section_name=course_section_name)
        all_assignments = self.get_assignments(course_group_name=course_group_name,
                                               course_section_name=course_section_name)
        course_section_info = self.get_course_section_info(course_section_name=course_section_name)

        submissions = []
        for assignment_id in submissions_dict:
            for student_id in submissions_dict[assignment_id]:
                submission = submissions_dict[assignment_id][student_id]

                # ----------------------------------------------------------------------------------
                # temporary assignment so it won't be None for testing (should be removed)
                submission['score'] = 100
                submission['posted_at'] = DateTime(2022, 9, 21, 17, 12, 10, tzinfo=Timezone('UTC'))
                submission['excused'] = False
                # ----------------------------------------------------------------------------------

                if assignment_id in all_assignments:
                    if student_id in all_students:
                        skip = submission['posted_at'] > plm.now()
                        submission = Submission(
                            lms_id=canvas_id,
                            student=all_students[student_id],
                            assignment=all_assignments[assignment_id],
                            score=submission['score'],
                            posted_at=submission['posted_at'],
                            late=submission['late'],
                            missing=submission['missing'],
                            excused=submission['excused'],
                            course_section_info=course_section_info,
                            grader=None,
                            status=SubmissionGradingStatus.NOT_ASSIGNED,
                            skip=skip
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
    def update_override(self, course_name: str, override: Override):
        pass

    # ---------------------------------------------------------------------------------------------------
    def create_overrides(self, course_section_name: str, assignment: Assignment, overrides: List[Override]):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        assignment_dict = {
            'id': assignment.lms_id,
            'name': assignment.name
        }
        outputs = []
        if overrides is not None:
            for override in overrides:
                override_dict = {
                    'student_ids': [student_id for student_id in override.students],
                    'unlock_at': override.unlock_at,
                    'due_at': override.due_at,
                    'lock_at': override.lock_at,
                    'title': override.name
                }
                output = _create_override(api_info=api_info, assignment=assignment_dict,
                                          override=override_dict)
                outputs.append(output)

        return overrides

    # ---------------------------------------------------------------------------------------------------
    def delete_overrides(self, course_section_name: str, assignment: Assignment, overrides: List[Override]):
        canvas_id = self.canvas_course_lms_ids[course_section_name]
        api_info = {
            'domain': self.canvas_base_domain,
            'id': canvas_id,
            'token': self.canvas_api_tokens[course_section_name]
        }
        assignment_dict = {
            'id': assignment.lms_id,
            'name': assignment.name
        }
        if overrides is not None:
            for override in overrides:
                override_dict = {
                    'id': override.lms_id,
                    'student_ids': [student_id for student_id in override.students],
                    'unlock_at': override.unlock_at,
                    'due_at': override.due_at,
                    'lock_at': override.lock_at,
                    'title': override.name
                }
                _remove_override(api_info=api_info, assignment=assignment_dict, override=override_dict)
        return overrides

    # ---------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    from rudaux.model.settings import Settings
    from rudaux.flows import load_settings
    import importlib


    def get_class_from_string(s):
        module_name, class_name = s.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)


    def get_learning_management_system(settings, group_name):
        LMS = get_class_from_string(settings.lms_classes[group_name])
        if not issubclass(LMS, LearningManagementSystem):
            raise ValueError
        lms = LMS.parse_obj(settings)
        return lms


    _config_path = "/home/alireza/Desktop/SES/rudaux/rudaux_config.yml"
    _group_name = "course_dsci_100_test"
    _course_name = "section_dsci_100_test_01"

    settings = load_settings(_config_path)
    print(settings)
    settings = Settings.parse_obj(settings)
    lms = get_learning_management_system(settings, group_name=_group_name)
    print()

    course_info = lms.get_course_section_info(course_section_name=_course_name)
    print('course_info: ', course_info, '\n')

    students = lms.get_students(course_section_name=_course_name)
    print('students: ', students, '\n')

    instructors = lms.get_instructors(course_section_name=_course_name)
    print('instructors: ', instructors, '\n')

    groups = lms.get_groups(course_section_name=_course_name)
    print('groups: ', groups, '\n')

    assignments = lms.get_assignments(course_group_name=_group_name, course_section_name=_course_name)
    print('assignments: ', assignments, '\n')

    submissions = lms.get_submissions(course_group_name=_group_name, course_section_name=_course_name,
                                      assignment=assignments['1292206'])
    print('submissions: ', submissions, '\n')

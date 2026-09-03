from loguru import logger

from pydantic import PrivateAttr
from typing import Dict, List, Optional, Any

from canvasapi import Canvas as C

import pendulum as plm
from pendulum import DateTime
from pendulum.tz.timezone import Timezone

from rudaux.interface.base.learning_management_system import LearningManagementSystem
from rudaux.interface.base.submission_system import SubmissionGradingStatus
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
    _canvas_api_instances: Any = PrivateAttr(default=None)
    assignments: Dict[str, dict]

    # ---------------------------------------------------------------------------------------------------
    def model_post_init(self, context: Any) -> None:
        self._canvas_api_instances = {}
        for section, id in self.canvas_course_lms_ids.items():
            self._canvas_api_instances[section] = C(self.canvas_base_domain,self.canvas_api_tokens[section]).get_course(self.canvas_course_lms_ids[section])

    # ---------------------------------------------------------------------------------------------------
    def open(self):
        pass

    # ---------------------------------------------------------------------------------------------------
    def close(self):
        pass

    # ---------------------------------------------------------------------------------------------------
    def get_course_section_info(self, course_section_name: str) -> CourseSectionInfo:
        section = self._canvas_api_instances[course_section_name]

        course_section_info = CourseSectionInfo(
                                                lms_id=str(section.id),
                                                name=section.name,
                                                code=section.course_code,
                                                start_at=None if section.start_at is None else plm.parse(section.start_at),
                                                end_at=None if section.end_at is None else plm.parse(section.end_at),
                                                time_zone=section.time_zone
                                               )
        
        logger.info(f"Retrieved course section info for {section.name}")
        logger.debug(f"Processed info {course_section_info}")
        if course_section_info.start_at is None or course_section_info.end_at is None:
            raise ValueError(f"Course start or end date has not been set for section {section.name}")
        elif course_section_info.start_at > plm.now():
            raise ValueError(f"Course start date is in the future.")
        elif course_section_info.end_at < plm.now():
            raise ValueError(f"Course has ended or end date incorrect.")

        return course_section_info

    # ---------------------------------------------------------------------------------------------------
    def get_students(self, course_section_name) -> Dict[str, Student]:
        section = self._canvas_api_instances[course_section_name]
        students = {}
        enrollments_dict = {e.user['id']:e for e in section.get_enrollments()}

        for s in section.get_users(enrollment_type=['student']):
            students[str(s.id)] = Student(
                                          lms_id=str(s.id), 
                                          name=s.name, 
                                          sortable_name=s.sortable_name, 
                                          school_id=s.sis_user_id, 
                                          reg_date=plm.parse(s.created_at) if s.created_at is not None else plm.parse(s.updated_at),
                                          status=enrollments_dict[s.id].enrollment_state
                                         )
            
        logger.info(f"Retrieved {len(students)} students from {section.name}")
        logger.debug(students)

        return students
    
    # ---------------------------------------------------------------------------------------------------
    def get_instructors(self, course_section_name: str) -> Dict[str, Instructor]:
        section = self._canvas_api_instances[course_section_name]
        instructors = {}
        enrollments_dict = {e.user['id']:e for e in section.get_enrollments()}

        for i in section.get_users(enrollment_type=['teacher']):
            instructors[str(i.id)] = Instructor(
                                                lms_id=str(i.id), 
                                                name=i.name, 
                                                sortable_name=i.sortable_name, 
                                                school_id=i.sis_user_id, 
                                                reg_date=plm.parse(i.created_at) if i.created_at is not None else plm.parse(i.updated_at),
                                                status=enrollments_dict[i.id].enrollment_state
                                               )
            
        logger.info(f"Retrieved {len(instructors)} instructors from {section.name}")
        logger.debug(instructors)

        return instructors

    # ---------------------------------------------------------------------------------------------------
    def get_tas(self, course_section_name: str):
        section = self._canvas_api_instances[course_section_name]
        tas = {}
        enrollments_dict = {e.user['id']:e for e in section.get_enrollments()}

        for t in section.get_users(enrollment_type=['ta']):
            tas[str(t.id)] = Instructor(
                                        lms_id=str(t.id), 
                                        name=t.name, 
                                        sortable_name=t.sortable_name, 
                                        school_id=t.sis_user_id, 
                                        reg_date=plm.parse(t.created_at) if t.created_at is not None else plm.parse(t.updated_at),
                                        status=enrollments_dict[t.id].enrollment_state
                                       )
            
        logger.info(f"Retrieved {len(tas)} TAs from {section.name}")
        logger.debug(tas)

        return tas

    # ---------------------------------------------------------------------------------------------------
    def get_groups(self, course_section_name: str):
        pass

    # ---------------------------------------------------------------------------------------------------
    def get_assignments(self, course_group_name: str, course_section_name: str) -> Dict[str, Assignment]:
        section = self._canvas_api_instances[course_section_name]
        assignments = {}

        course_section_info = self.get_course_section_info(course_section_name)
        students = self.get_students(course_section_name)

        for a in section.get_assignments():
            if a.name not in list(self.assignments.values())[0]:
                continue

            assignments[str(a.id)] = Assignment(
                                                lms_id=str(a.id),
                                                name=a.name,
                                                due_at=plm.parse(a.due_at) if a.due_at is not None else None,
                                                lock_at=plm.parse(a.lock_at) if a.lock_at is not None else None,
                                                unlock_at=plm.parse(a.unlock_at) if a.unlock_at is not None else None,
                                                overrides={str(o.id):Override(
                                                                              lms_id=str(o.id),
                                                                              name=o.title,
                                                                              due_at=plm.parse(o.due_at) if o.due_at is not None else None,
                                                                              lock_at=plm.parse(o.lock_at) if o.lock_at is not None else None,
                                                                              unlock_at=plm.parse(o.unlock_at) if o.unlock_at is not None else None,
                                                                              students={str(sid):students[str(sid)] for sid in o.student_ids} if hasattr(o, 'student_ids') else None,
                                                                              course_section_id=str(o.course_section_id) if hasattr(o, 'course_section_id') else None,
                                                                              course_section_info=course_section_info,
                                                                              assignment_id=str(a.id)
                                                                             ) for o in a.get_overrides()},
                                                only_visible_to_overrides=a.only_visible_to_overrides,
                                                published=a.published,
                                                course_section_info=course_section_info,
                                                skip=plm.parse(a.due_at) > plm.now() if a.due_at is not None else True
                                               )
        
        logger.info(f"Retrieved {len(assignments)} assignments from {section.name}")
        logger.debug(assignments)

        ids = [a.lms_id for a in assignments.values()]
        names = [a.name for a in assignments.values()]

        if len(set(ids)) != len(ids):
            raise ValueError(f"Course ID {str(section.id)}: Two assignments detected with the same ID. IDs: {ids}")
        if len(set(names)) != len(names):
            raise ValueError(f"Course ID {str(section.id)}: Two assignments detected with the same name. Names: {names}")
        if len(names) < len(list(self.assignments.values())[0]):
            raise ValueError(f"Assignments from config missing in the course LMS.\nConfig: {list(self.assignments.values())[0]}\nLMS: {names}")

        return(assignments)

    # ---------------------------------------------------------------------------------------------------
    def get_submissions(self, course_group_name: str, course_section_name: str, assignment: Assignment) -> List[Submission]:
        section = self._canvas_api_instances[course_section_name]
        submissions = []

        course_section_info = self.get_course_section_info(course_section_name)
        students = self.get_students(course_section_name)

        for s in section.get_assignment(int(assignment.lms_id)).get_submissions():
            # Filter out non-existent students e.g. Test Student
            if str(s.user_id) not in students:
                continue

            submission = Submission(
                                    lms_id=str(s.id),
                                    student=students[str(s.user_id)],
                                    assignment=assignment,
                                    score=s.score,
                                    posted_at=plm.parse(s.posted_at) if s.posted_at is not None else None,
                                    late=s.late,
                                    missing=s.missing,
                                    excused=s.excused if s.excused is not None else False,
                                    course_section_info=course_section_info,
                                    grader=None,
                                    status=SubmissionGradingStatus.NOT_ASSIGNED,
                                    skip=True if s.posted_at is not None else False
                                   )
            
            submissions.append(submission)

        logger.info(f"Retrieved {len(submissions)} submissions for {assignment.name}")
        logger.debug(submissions)

        return submissions
        
    # ---------------------------------------------------------------------------------------------------
    def update_grade(self, course_section_name: str, submission: Submission):
        section = self._canvas_api_instances[course_section_name]
        canvas_submission = section.get_assignment(submission.assignment.lms_id).get_submission(submission.student.lms_id)

        if canvas_submission.score is not None:
            logger.warning(f'Grade already set to {canvas_submission.score} for {submission.assignment.name}, student: {submission.student.name} - {submission.student.lms_id}')
            logger.warning(f'Reset student grade to - (no grade) on Canvas if current grade is incorrect')
            return

        canvas_submission.edit(submission={'posted_grade':submission.score})

        # Confirm uploaded grade
        canvas_submission = section.get_assignment(submission.assignment.lms_id).get_submission(submission.student.lms_id)
        if abs(float(submission.score) - float(canvas_submission.score)) > 0.01:
            raise ValueError(f"Grade {submission.score} failed to upload for submission {submission.assignment.name} by student {submission.student.name} - {submission.student.lms_id}; grade on canvas is {canvas_submission.score}")
        
        logger.info(f'Uploaded grade {canvas_submission.score} for {submission.assignment.name}, student: {submission.student.name} - {submission.student.lms_id}')

    # ---------------------------------------------------------------------------------------------------
    def update_override(self, course_section_name: str, override: Override):
        section = self._canvas_api_instances[course_section_name]
        canvas_assignment = section.get_assignment(override.assignment_id)
        canvas_override = canvas_assignment.get_override(override.lms_id)

        canvas_override.edit(assignment_override={
                                                  'student_ids':[int(id) for id in override.students.keys()],
                                                  'title':override.name,
                                                  'due_at':override.due_at, 
                                                  'unlock_at':override.unlock_at, 
                                                  'lock_at':override.lock_at
                                                 })
        
        logger.info(f"Updated override for {canvas_assignment.name} in {course_section_name} \n\n {override} \n")

    # ---------------------------------------------------------------------------------------------------
    def create_overrides(self, course_section_name: str, overrides: List[Override]):
        section = self._canvas_api_instances[course_section_name]

        for o in overrides:
            a = section.get_assignment(o.assignment_id)
            canvas_override = a.create_override(assignment_override={
                                                   'student_ids':[int(id) for id in o.students.keys()],
                                                   'title':o.name,
                                                   'due_at':o.due_at,
                                                   'unlock_at':o.unlock_at,
                                                   'lock_at':o.lock_at
                                                  })
            o.lms_id = str(canvas_override.id)
            logger.info(f'Created override for {a.name} in {course_section_name} \n\n {o} \n')

        
    # ---------------------------------------------------------------------------------------------------
    def delete_overrides(self, course_section_name: str, overrides: List[Override]):
        section = self._canvas_api_instances[course_section_name]

        for o in overrides:
            a = section.get_assignment(o.assignment_id)
            a.get_override(o.lms_id).delete()
            logger.info(f'Deleted override for {a.name} in {course_section_name} \n\n {o} \n')

    
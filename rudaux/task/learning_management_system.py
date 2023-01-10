from typing import List, Dict
from prefect import task
from prefect import get_run_logger
from ..model import Student, Assignment, CourseSectionInfo, Override, Submission, Instructor
from rudaux.interface.base.learning_management_system import LearningManagementSystem as LMS


# -----------------------------------------------------------------------------------------
# wraps the lms.get_students function in a task and enforces validation
# @task
def get_students(lms: LMS, course_section_name: str) -> Dict[str, Student]:
    students = lms.get_students(course_section_name=course_section_name)
    for student_id, student in students.items():
        if not isinstance(student, Student):
            raise ValueError
    return students


# -----------------------------------------------------------------------------------------
# wraps the lms.get_instructors function in a task and enforces validation
# @task
def get_instructors(lms: LMS, course_section_name: str) -> Dict[str, Instructor]:
    instructors = lms.get_instructors(course_section_name=course_section_name)
    for instructor_id, instructor in instructors:
        if not isinstance(instructor, Instructor):
            raise ValueError
    return instructors


# -----------------------------------------------------------------------------------------

# wraps the lms.get_assignments function in a task and enforces validation
# @task
def get_assignments(lms: LMS, course_group_name: str, course_section_name: str) -> Dict[str, Assignment]:
    assignments = lms.get_assignments(course_group_name=course_group_name,
                                      course_section_name=course_section_name)
    for assignment_id, assignment in assignments.items():
        if not isinstance(assignment, Assignment):
            raise ValueError
    return assignments


# -----------------------------------------------------------------------------------------

# wraps the lms.get_course_info function in a task and enforces validation
# @task
def get_course_section_info(lms: LMS, course_section_name: str) -> CourseSectionInfo:
    course_info = lms.get_course_section_info(course_section_name=course_section_name)
    if not isinstance(course_info, CourseSectionInfo):
        raise ValueError
    return course_info


# -----------------------------------------------------------------------------------------

# wraps the lms.get_course_info function in a task and enforces validation
# @task
def get_submissions(lms: LMS, course_group_name: str,
                    course_section_name: str, assignment: dict) -> List[Submission]:
    submissions = lms.get_submissions(course_group_name=course_group_name,
                                      course_section_name=course_section_name,
                                      assignment=assignment)
    for sub in submissions:
        if not isinstance(sub, Submission):
            raise ValueError
    return submissions


# -----------------------------------------------------------------------------------------

# wraps the lms.update_override function in a task and enforces validation
# @task
def update_override(lms: LMS, course_section_name: str, override: Override) -> Override:
    override = lms.update_override(course_section_name=course_section_name, override=override)
    if not isinstance(override, Override):
        raise ValueError
    return override


# -----------------------------------------------------------------------------------------

# wraps the lms.create_overrides function in a task and enforces validation
# @task
def create_overrides(lms: LMS, course_section_name: str, assignment: Assignment,
                     overrides: List[Override]) -> List[Override]:

    overrides = lms.create_overrides(course_section_name=course_section_name,
                                     assignment=assignment, overrides=overrides)
    for override in overrides:
        if not isinstance(override, Override):
            raise ValueError
    return overrides


# -----------------------------------------------------------------------------------------

# wraps the lms.delete_overrides function in a task and enforces validation
# @task
def delete_overrides(lms: LMS, course_section_name: str, assignment: Assignment,
                     overrides: List[Override]) -> List[Override]:

    overrides = lms.delete_overrides(course_section_name=course_section_name,
                                     assignment=assignment, overrides=overrides)

    for override in overrides:
        if not isinstance(override, Override):
            raise ValueError
    return overrides


# -----------------------------------------------------------------------------------------

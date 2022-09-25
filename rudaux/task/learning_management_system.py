from prefect import task
from ..model import Student, Assignment, CourseInfo, Override, Submission


# wraps the lms.get_students function in a task and enforces validation
@task
def get_students(lms):
    students = lms.get_students()
    for stu in students:
        if not isinstance(stu, Student):
            raise ValueError
    return students


# wraps the lms.get_assignments function in a task and enforces validation
@task
def get_assignments(lms):
    assignments = lms.get_assignments()
    for asgn in assignments:
        if not isinstance(asgn, Assignment):
            raise ValueError
    return assignments


# wraps the lms.get_course_info function in a task and enforces validation
@task
def get_course_info(lms):
    ci = lms.get_course_info()
    if not isinstance(ci, CourseInfo):
        raise ValueError
    return ci


# wraps the lms.get_course_info function in a task and enforces validation
@task
def get_submissions(lms):
    submissions = lms.get_submissions()
    for sub in submissions:
        if not isinstance(sub, Submission):
            raise ValueError
    return submissions

# wraps the lms.update_override function in a task and enforces validation
@task
def update_override(lms):
    override = lms.update_override()
    if not isinstance(override, Override):
        raise ValueError
    return override


# wraps the lms.create_overrides function in a task and enforces validation
@task
def create_overrides(lms):
    overrides = lms.create_overrides()
    for override in overrides:
        if not isinstance(override, Override):
            raise ValueError
    return overrides


# wraps the lms.delete_overrides function in a task and enforces validation
@task
def delete_overrides(lms):
    overrides = lms.delete_overrides()
    for override in overrides:
        if not isinstance(override, Override):
            raise ValueError
    return overrides

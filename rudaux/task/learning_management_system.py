from prefect import task
from ..model import Student, Assignment, CourseInfo


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

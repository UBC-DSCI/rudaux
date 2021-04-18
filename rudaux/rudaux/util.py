from prefect import Flow, unmapped, flatten, task
from prefect.engine import signals

@task
def build_submission_triplet(assignments, students, submission):
    assignment = None
    student = None
    for asgn in assignments:
        if asgn['id'] == submission['assignment_id']:
            assignment = asgn
        break
    for stu in students:
        if stu['id'] == submission['student_id']:
            student = stu
        break

    if assignment is None or student is None:
        sig = signals.FAIL(f'Failed to find assignment (found {assignment}) or student (found {student}) corresponding to submission {submission}')
        sig.assignment = assignment
        sig.student = student
        sig.submission = submission
        raise sig
 
    return (assignment, student, submission)


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
        sig = signals.FAIL(f'Failed to find assignment (found {assignment}) or student (found {student}) corresponding to submission {submission}. \n Assignments {assignments} \n Students {students}')
        
        sig.assignment = assignment
        sig.student = student
        sig.submission = submission
        raise sig
 
    return (assignment, student, submission)

@task
def build_assignment_student_pairs(assignments, students):
    return [(a, s) for a in assignments for s in students]

@task(nout=2)
def reduce_override_pairs(override_create_remove_pairs):
    to_create = [pair[0] for pair in override_create_remove_pairs]
    to_remove = [pair[1] for pair in override_create_remove_pairs]
    return to_create, to_remove

@task
def combine_dictionaries(dicts):
    return {k : v for d in dicts for k, v in d.items()}

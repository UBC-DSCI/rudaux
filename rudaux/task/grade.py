from typing import List, Tuple
import pendulum as plm
import getpass
import prefect
from prefect import task, get_run_logger
from rudaux.interface import GradingSystem, LearningManagementSystem
from rudaux.interface.base.grading_system import GradingStatus
from rudaux.model import Settings
from rudaux.model.submission import Submission
from rudaux.model.assignment import Assignment
from rudaux.model.grader import Grader


@task
def build_grading_team(settings: Settings, grading_system: GradingSystem,
                       course_group: str, assignment_name: str,
                       assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]) -> List[Grader]:
    logger = get_run_logger()

    skip = False
    for section_assignment, section_submissions in assignment_submissions_pairs:

        # start by checking whether any of the assignment deadlines are in the future. If so, skip.
        # skip the section assignment if it isn't due yet
        # if section_assignment.due_at > plm.now():
        if section_assignment.skip:
            logger.info(f"Assignment {section_assignment.name} ({section_assignment.lms_id}) "
                        f"due date {section_assignment.due_at} is in the future. Skipping.")
            skip = True
            break
            # check the skip and create grader still but set the skip of that to true as well

        # check whether all grades have been posted (assignment is done). If so, skip
        all_posted = True
        all_posted = all_posted and all([submission.posted_at is not None for submission in section_submissions])

        if all_posted:
            logger.info(f"All grades are posted for assignment {section_assignment.name}. Workflow done. Skipping.")
            skip = True
            break

    config_users = settings.assignments[course_group][assignment_name]
    graders = []

    for user in config_users:
        grader = grading_system.build_grader(
            course_name=course_group,
            assignment_name=assignment_name,
            username=user,
            skip=skip)

        graders.append(grader)

    return graders


# ----------------------------------------------------------------------------------------------------------
@task
def generate_assignments(grading_system: GradingSystem, grader: Grader):
    if not grader.skip:
        grading_system.generate_assignment(grader=grader)


# ----------------------------------------------------------------------------------------------------------
@task
def generate_solutions(grading_system: GradingSystem, grader: Grader):
    logger = get_run_logger()
    if not grader.skip:
        grading_system.generate_solution(grader=grader)


# ----------------------------------------------------------------------------------------------------------
@task
def initialize_graders(grading_system: GradingSystem, graders: List[Grader]):
    logger = get_run_logger()
    for grader in graders:
        if not grader.skip:
            grading_system.initialize_grader(grader=grader)
    return graders


# ----------------------------------------------------------------------------------------------------------
# submission tasks
# ----------------------------------------------------------------------------------------------------------
@task
def assign_graders(grading_system: GradingSystem, graders: List[Grader],
                   assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.assign_submission_to_grader(graders=graders, submission=submission)
            submission.grader.info['status'] = GradingStatus.ASSIGNED

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def collect_submissions(grading_system: GradingSystem,
                        assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]],
                        lms: LearningManagementSystem):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:

            grading_system.collect_grader_submissions(submission=submission)

            # if the submission is due in the future, skip
            # if submission.posted_at > plm.now():
            if submission.skip:
                submission.grader.status = GradingStatus.NOT_DUE
                continue

            if submission.grader.status == GradingStatus.MISSING:
                if submission.score is None:
                    logger.info(f"Submission {submission.lms_id} is missing. Uploading score of 0.")
                    submission.score = 0.
                    lms.update_grade(course_section_name=submission.course_section_info.name,
                                     submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def clean_submissions(grading_system: GradingSystem,
                      assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:

            if submission.grader.status == GradingStatus.COLLECTED:
                student = submission.student
                grader = submission.grader

                grading_system.clean_grader_submission(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def autograde(grading_system: GradingSystem,
              assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.autograde(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------

@task
def check_manual_grading(grading_system: GradingSystem,
                         assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.get_needs_manual_grading(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
# feedback tasks
# ----------------------------------------------------------------------------------------------------------

@task
def generate_feedback(grading_system: GradingSystem,
                      assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.generate_feedback(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def return_feedback(settings: Settings, grading_system: GradingSystem,
                    pastdue_frac: float,
                    assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    assignment_name = assignment_submissions_pairs[0][0].name
    # skip if pastdue frac not high enough, or we haven't reached the earliest return date
    if pastdue_frac < settings.return_solution_threshold:
        msg = f"Assignment {assignment_name} has {pastdue_frac} submissions " \
              f"past their due date, which is less than the return solution " \
              f"threshold {settings.return_solution_threshold}. " \
              f"Skipping feedback return."
        # raise signals.SKIP(msg)
    if plm.now() < plm.parse(settings.earliest_solution_return_date):
        msg = f"We have not yet reached the earliest solution return date " \
              f"{settings.earliest_solution_return_date}. Skipping feedback return."
        # raise signals.SKIP(msg)

    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.return_feedback(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def get_pastdue_fraction(assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    num_total_assignments = 0.
    num_outstanding_assignments = 0.
    for section_assignment, section_submissions in assignment_submissions_pairs:
        num_total_assignments += len(section_submissions)
        num_outstanding_assignments += len(
            [None for submission in section_submissions if submission.assignment.due_at > plm.now()])
    return (num_total_assignments - num_outstanding_assignments) / num_total_assignments


# ----------------------------------------------------------------------------------------------------------
@task
def collect_grading_notifications(assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    notifications = {}
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            assignment = section_assignment
            grader = submission.grader
            if grader.status == GradingStatus.NEEDS_MANUAL_GRADE:
                grader_user = grader.info['user']
                grader_name = grader.name
                assignment_name = assignment.name
                if grader_user not in notifications:
                    notifications[grader_user] = {}
                if grader_name not in notifications[grader_user]:
                    notifications[grader_user][grader_name] = {'assignment': assignment_name, 'count': 0}
                notifications[grader_user][grader_name]['count'] += 1
    return notifications


# ----------------------------------------------------------------------------------------------------------
@task
def await_completion(assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    all_done = True
    logger = get_run_logger()
    assignment_name = assignment_submissions_pairs[0][0].name
    for section_assignment, section_submissions in assignment_submissions_pairs:
        all_done = all_done and all(
            [submission.grader.status != GradingStatus.NEEDS_MANUAL_GRADE for submission in section_submissions])
    if not all_done:
        msg = f"Assignment {assignment_name} not done grading yet. " \
              f"Skipping uploading grades / returning feedback"
        logger.info(msg)
        # raise signals.SKIP(msg)
    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def upload_grades(grading_system: GradingSystem, lms: LearningManagementSystem,
                  assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:

            student = submission.student
            assignment = submission.assignment
            course_section_info = submission.course_section_info
            grader = submission.grader

            if grader.status == GradingStatus.DONE_GRADING and submission.score is None:
                pct = grading_system.compute_submission_percent_grade(submission=submission)
                logger.info(f"Uploading to Canvas...")
                submission.score = pct
                lms.update_grade(course_section_name=submission.course_section_info.name,
                                 submission=submission)
    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task
def collect_posting_notifications(assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    notifications = []
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            assignment = section_assignment
            grader = submission.grader
            course_name = submission.course_section_info.name
            if grader.status == GradingStatus.DONE_GRADING and submission.posted_at is None:
                notifications.append((course_name, assignment.name))
    return notifications

# ----------------------------------------------------------------------------------------------------------

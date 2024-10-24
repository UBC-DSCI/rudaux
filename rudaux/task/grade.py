from typing import List, Tuple
import pendulum as plm
import getpass
import prefect
from prefect import task, get_run_logger
from rudaux.interface import GradingSystem, LearningManagementSystem
from rudaux.interface.base.submission_system import SubmissionGradingStatus
from rudaux.model import Settings
from rudaux.model.submission import Submission
from rudaux.model.assignment import Assignment
from rudaux.model.grader import Grader
from rudaux.util.util import signal, State


@task(name='build_grading_team')
@signal
def build_grading_team(state: State, settings: Settings, grading_system: GradingSystem,
                       course_group: str, assignment_name: str,
                       assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]
                       ) -> List[Grader]:
    logger = get_run_logger()

    state.skip = False
    for section_assignment, section_submissions in assignment_submissions_pairs:

        # start by checking whether any of the assignment deadlines are in the future. If so, skip.
        # skip the section assignment if it isn't due yet
        # if section_assignment.due_at > plm.now():
        if section_assignment.skip:
            logger.info(f"Assignment {section_assignment.name} ({section_assignment.lms_id}) "
                        f"due date {section_assignment.due_at} is in the future. Skipping.")
            state.skip = True
            break
            # check the skip and create grader still but set the skip of that to true as well

        # check whether all grades have been posted (assignment is done). If so, skip
        all_posted = True
        all_posted = all_posted and all([submission.posted_at is not None for submission in section_submissions])

        if all_posted:
            logger.info(f"All grades are posted for assignment {section_assignment.name}. Workflow done. Skipping.")
            state.skip = True
            break

    config_users = settings.assignments[course_group][assignment_name]
    graders = []

    for user in config_users:
        grader = grading_system.build_grader(
            course_name=course_group,
            assignment_name=assignment_name,
            username=user,
            skip=state.skip)

        graders.append(grader)

    return graders


# ----------------------------------------------------------------------------------------------------------
@task(name='generate_assignments')
@signal
def generate_assignments(state: State, grading_system: GradingSystem, grader: Grader):
    # if not grader.skip:
    grading_system.generate_assignment(grader=grader)
    return grader


# ----------------------------------------------------------------------------------------------------------
@task(name='generate_solutions')
@signal
def generate_solutions(state: State, grading_system: GradingSystem, grader: Grader):
    # logger = get_run_logger()
    # if not grader.skip:
    grading_system.generate_solution(grader=grader)
    return grader


# ----------------------------------------------------------------------------------------------------------
@task(name='initialize_graders')
@signal
def initialize_graders(state: State, grading_system: GradingSystem, graders: List[Grader]):
    # logger = get_run_logger()
    graders = [grader for grader in graders if not grader.skip]
    graders = grading_system.initialize_graders(graders=graders)
    return graders


# ----------------------------------------------------------------------------------------------------------
# submission tasks
# ----------------------------------------------------------------------------------------------------------
@task(name='assign_graders')
@signal
def assign_graders(state: State, grading_system: GradingSystem, graders: List[Grader],
                   assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                grading_system.assign_submission_to_grader(graders=graders, submission=submission)
                submission.status = SubmissionGradingStatus.ASSIGNED

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='return_solutions')
@signal
def return_solutions(state: State,
                     grading_system: GradingSystem,
                     pastdue_fraction: float,
                     return_solution_threshold: float,
                     earliest_solution_return_date,
                     assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):

    logger = get_run_logger()

    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:

                assignment = submission.assignment
                student = submission.student

                # skip if pastdue frac not high enough, or we haven't reached the earliest return date
                if pastdue_fraction < return_solution_threshold:
                    logger.info(f"Assignment {assignment.name} has {pastdue_fraction} submissions " +
                                f"past their due date, which is less than the return solution " +
                                f"threshold {return_solution_threshold} . Skipping solution return.")
                    state.skip = True
                if plm.now() < plm.parse(earliest_solution_return_date):
                    logger.info(f"We have not yet reached the earliest solution return date " +
                                f"{earliest_solution_return_date}. Skipping solution return.")
                    state.skip = True

                grading_system.return_solution(submission=submission)


# ----------------------------------------------------------------------------------------------------------
@task(name='collect_submissions')
@signal
def collect_submissions(state: State, grading_system: GradingSystem,
                        assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]],
                        lms: LearningManagementSystem):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:

            if not submission.grader.skip:
                grading_system.collect_grader_submissions(submission=submission)

                # if the submission is due in the future, skip
                # if submission.posted_at > plm.now():
                if submission.skip:
                    submission.status = SubmissionGradingStatus.NOT_DUE
                    continue

                if submission.status == SubmissionGradingStatus.MISSING:
                    if submission.score is None:
                        logger.info(f"Submission {submission.lms_id} is missing. Uploading score of 0.")
                        submission.score = 0.
                        lms.update_grade(course_section_name=submission.course_section_info.name,
                                         submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='clean_submissions')
@signal
def clean_submissions(state: State, grading_system: GradingSystem,
                      assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:

            if not submission.grader.skip:
                if submission.status == SubmissionGradingStatus.COLLECTED:
                    # student = submission.student
                    # grader = submission.grader
                    grading_system.clean_grader_submission(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='autograde')
@signal
def autograde(state: State, grading_system: GradingSystem,
              assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                grading_system.autograde(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------

@task(name='check_manual_grading')
@signal
def check_manual_grading(state: State, grading_system: GradingSystem,
                         assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                grading_system.get_needs_manual_grading(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
# feedback tasks
# ----------------------------------------------------------------------------------------------------------

@task(name='generate_feedback')
@signal
def generate_feedback(state: State, grading_system: GradingSystem,
                      assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                grading_system.generate_feedback(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='return_feedback')
@signal
def return_feedback(state: State, settings: Settings, grading_system: GradingSystem,
                    pastdue_fraction: float,
                    assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    assignment_name = assignment_submissions_pairs[0][0].name
    # skip if pastdue frac not high enough, or we haven't reached the earliest return date
    if pastdue_fraction < settings.return_solution_threshold:
        msg = f"Assignment {assignment_name} has {pastdue_fraction} submissions " \
              f"past their due date, which is less than the return solution " \
              f"threshold {settings.return_solution_threshold}. " \
              f"Skipping feedback return."
        logger.info(msg)
        state.skip = True
        # raise signals.SKIP(msg)
    if plm.now() < plm.parse(settings.earliest_solution_return_date):
        msg = f"We have not yet reached the earliest solution return date " \
              f"{settings.earliest_solution_return_date}. Skipping feedback return."
        logger.info(msg)
        state.skip = True
        # raise signals.SKIP(msg)

    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                grading_system.return_feedback(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='get_pastdue_fraction')
@signal
def get_pastdue_fraction(
        state: State,
        assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]) -> float:
    num_total_assignments = 0.
    num_outstanding_assignments = 0.
    for section_assignment, section_submissions in assignment_submissions_pairs:
        num_total_assignments += len(section_submissions)
        num_outstanding_assignments += len(
            [None for submission in section_submissions if submission.assignment.due_at > plm.now()])
    return (num_total_assignments - num_outstanding_assignments) / num_total_assignments


# ----------------------------------------------------------------------------------------------------------
@task(name='collect_grading_notifications')
@signal
def collect_grading_notifications(
        state: State, assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    notifications = {}
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                assignment = section_assignment
                grader = submission.grader
                if submission.status == SubmissionGradingStatus.NEEDS_MANUAL_GRADE:
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
@task(name='await_completion')
@signal
def await_completion(
        state: State, assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    all_done = True
    logger = get_run_logger()
    assignment_name = assignment_submissions_pairs[0][0].name
    for section_assignment, section_submissions in assignment_submissions_pairs:
        all_done = all_done and all(
            [submission.status != SubmissionGradingStatus.NEEDS_MANUAL_GRADE
             for submission in section_submissions if not submission.grader.skip])
    if not all_done:
        msg = f"Assignment {assignment_name} not done grading yet. " \
              f"Skipping uploading grades / returning feedback"
        logger.info(msg)
        state.skip = True
        # raise signals.SKIP(msg)
    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='upload_grades')
@signal
def upload_grades(state: State, grading_system: GradingSystem, lms: LearningManagementSystem,
                  assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                # student = submission.student
                # assignment = submission.assignment
                # course_section_info = submission.course_section_info
                grader = submission.grader

                if submission.status == SubmissionGradingStatus.DONE_GRADING and submission.score is None:
                    pct = grading_system.compute_submission_percent_grade(submission=submission)
                    logger.info(f"Uploading to Canvas...")
                    submission.score = pct
                    lms.update_grade(course_section_name=submission.course_section_info.name,
                                     submission=submission)
    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------
@task(name='collect_posting_notifications')
@signal
def collect_posting_notifications(
        state: State, assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    # logger = get_run_logger()
    notifications = []
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            if not submission.grader.skip:
                assignment = section_assignment
                grader = submission.grader
                course_name = submission.course_section_info.name
                if submission.status == SubmissionGradingStatus.DONE_GRADING and submission.posted_at is None:
                    notifications.append((course_name, assignment.name))
    return notifications

# ----------------------------------------------------------------------------------------------------------
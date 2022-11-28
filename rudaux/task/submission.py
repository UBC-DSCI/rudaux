import json
import shutil
from enum import IntEnum
from json import JSONDecodeError
from typing import List, Tuple

from prefect.exceptions import PrefectSignal
import os
from prefect import task, get_run_logger
import pendulum as plm

from rudaux.interface import LearningManagementSystem, GradingSystem
from rudaux.model import Settings
from rudaux.model.grader import Grader
from rudaux.old_code.submission import GradingStatus
from rudaux.util.util import recursive_chown
from rudaux.model.submission import Submission
from rudaux.model.assignment import Assignment


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
@task
def generate_feedback(grading_system: GradingSystem,
                      assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
    logger = get_run_logger()
    for section_assignment, section_submissions in assignment_submissions_pairs:
        for submission in section_submissions:
            grading_system.generate_feedback(submission=submission)

    return assignment_submissions_pairs


# ----------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------
@task
def return_feedback(config, pastdue_frac, subm_set):
    logger = get_run_logger()
    # skip if pastdue frac not high enough or we haven't reached the earlist return date
    if pastdue_frac < config.return_solution_threshold:
        raise signals.SKIP(f"Assignment {subm_set['__name__']} has {pastdue_frac} submissions " +
                           f"past their due date, which is less than the return soln " +
                           f"threshold {config.return_solution_threshold} . Skipping feedback return.")
    if plm.now() < plm.parse(config.earliest_solution_return_date):
        raise signals.SKIP(f"We have not yet reached the earliest solution return date " +
                           f"{config.earliest_solution_return_date}. Skipping feedback return.")

    for course_name in subm_set:
        if course_name == '__name__':
            continue
        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            # logger.info(f"Checking whether feedback for submission {subm['name']} can be returned")
            if subm['due_at'] < plm.now() and subm['status'] != GradingStatus.MISSING:
                if not os.path.exists(subm['generated_feedback_path']):
                    logger.warning(f"Warning: feedback file {subm['generated_feedback_path']} "
                                   f"doesnt exist yet. Skipping feedback return.")
                    continue
                if not os.path.exists(subm['fdbk_path']):
                    logger.info(f"Returning feedback for submission {subm['name']}")
                    if os.path.exists(subm['student_folder']):
                        shutil.copy(subm['generated_feedback_path'], subm['fdbk_path'])
                        recursive_chown(subm['fdbk_path'], subm['grader']['unix_user'], subm['grader']['unix_group'])
                    else:
                        logger.warning(f"Warning: student folder {subm['student_folder']} "
                                       f"doesnt exist. Skipping feedback return.")
            # else:
            #    logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
    return

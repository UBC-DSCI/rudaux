from typing import List, Tuple
import pendulum as plm
import getpass
import prefect
from prefect import task, get_run_logger
from prefect.exceptions import PrefectSignal
import os
from subprocess import check_output, STDOUT, CalledProcessError
from dictauth.users import add_user, remove_user, get_users
from collections import namedtuple
import git
import shutil
from rudaux.interface import GradingSystem
from rudaux.model import Settings
from rudaux.util.container import run_container
from rudaux.util.util import get_logger, recursive_chown
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


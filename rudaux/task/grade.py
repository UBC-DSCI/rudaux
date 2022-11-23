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

    for section_assignment, section_submissions in assignment_submissions_pairs:

        # start by checking whether any of the assignment deadlines are in the future. If so, skip.
        # skip the section assignment if it isn't due yet
        if section_assignment.due_at > plm.now():
            logger.info(f"Assignment {section_assignment.name} ({section_assignment.lms_id}) "
                        f"due date {section_assignment.due_at} is in the future. Skipping.")
            continue

        # check whether all grades have been posted (assignment is done). If so, skip
        all_posted = True
        all_posted = all_posted and all([submission.posted_at is not None for submission in section_submissions])

        if all_posted:
            logger.info(f"All grades are posted for assignment {section_assignment.name}. Workflow done. Skipping.")
            continue

    # get list of users from dictauth
    users = grading_system.get_users()
    config_users = settings.assignments[course_group][assignment_name]
    graders = []

    for user in config_users:
        # ensure user exists
        if user not in users:
            msg = f"User account {user} listed in rudaux_config does not exist in dictauth: {users} . " \
                  f"Make sure to use dictauth to create a grader account for each of the " \
                  f"TA/instructors listed in config.assignments"
            logger.error(msg)
            raise PrefectSignal

        grader = grading_system.build_grader(
            course_name=course_group, assignment_name=assignment_name, username=user)
        graders.append(grader)

    return graders


# ----------------------------------------------------------------------------------------------------------
@task
def create_grading_volume(grader: Grader):
    logger = get_run_logger()
    # create the zfs volume
    if not os.path.exists(grader.info['folder']):
        logger.info(f"Grader folder {grader.info['folder']} doesn't exist, creating...")
        try:
            zfs_path = "/usr/sbin/zfs"
            check_output(['sudo', zfs_path, 'create', "-o", "refquota=" + grader.info['unix_quota'],
                          grader.info['folder'].lstrip('/')], stderr=STDOUT)
        except CalledProcessError as e:
            msg = f"Error running command {e.cmd}. return_code {e.returncode}. " \
                  f"output {e.output}. stdout {e.stdout}. stderr {e.stderr}"
            logger.error(msg)
            raise PrefectSignal
        logger.info("Created!")


# ----------------------------------------------------------------------------------------------------------
@task
def clone_git_repository(settings: Settings, grader: Grader):
    logger = get_run_logger()
    # clone the git repository
    # TODO if there's an error cloning the repo or an unknown error when doing the initial test repo create
    # email instructor and print a message to tell the user to create a deploy key
    repo_valid = False
    # allow no such path or invalid repo errors; everything else should raise
    try:
        tmp_repo = git.Repo(grader.info['folder'])
    except git.exc.InvalidGitRepositoryError as e:
        pass
    except git.exc.NoSuchPathError as e:
        pass
    else:
        repo_valid = True
    if not repo_valid:
        logger.info(f"{grader.info['folder']} is not a valid course repo. "
                    f"Cloning course repository from {settings.instructor_repo_url}")
        git.Repo.clone_from(settings.instructor_repo_url, grader.info['folder'])
        logger.info("Cloned!")


# ----------------------------------------------------------------------------------------------------------
@task
def create_submission_folder(grader: Grader):
    # create the submissions folder
    if not os.path.exists(grader.info['submissions_folder']):
        os.makedirs(grader.info['submissions_folder'], exist_ok=True)
    # reassign ownership to jupyter user
    recursive_chown(grader.info['folder'], grader.info['unix_user'], grader.info['unix_group'])


# ----------------------------------------------------------------------------------------------------------
@task
def generate_assignments(grading_system: GradingSystem, grader: Grader):
    logger = get_run_logger()
    # if the assignment hasn't been generated yet, generate it
    assignment_name = grader.info['assignment_name']
    generated_assignments = grading_system.get_generated_assignments(work_dir=grader.info['folder'])

    if assignment_name not in generated_assignments['log']:
        logger.info(f"Assignment {assignment_name} not yet generated for grader {grader.info['name']}")
        output = grading_system.generate_assignment(
            assignment_name=assignment_name, work_dir=grader.info['folder'])
        logger.info(output['log'])

        if 'ERROR' in output['log']:
            msg = f"Error generating assignment {assignment_name} for grader " \
                  f"{grader.info['name']} at path {grader.info['folder']}"
            logger.error(msg)
            raise PrefectSignal


# ----------------------------------------------------------------------------------------------------------
@task
def generate_solutions(grading_system: GradingSystem, grader: Grader):
    logger = get_run_logger()
    assignment_name = grader.info['assignment_name']
    # if the solution hasn't been generated yet, generate it
    if not os.path.exists(grader.info['solution_path']):
        logger.info(f"Solution for {assignment_name} not yet generated for grader {grader.info['name']}")
        output = grading_system.generate_solution(
            local_source_path=grader.info['local_source_path'],
            solution_name=grader.info['solution_name'],
            work_dir=grader.info['folder']
        )
        logger.info(output['log'])

        if 'ERROR' in output['log']:
            msg = f"Error generating solution for {assignment_name} for grader " \
                  f"{grader.info['name']} at path {grader.info['folder']}"
            logger.error(msg)
            raise PrefectSignal

    # transfer ownership to the jupyterhub user
    recursive_chown(grader.info['folder'], grader.info['unix_user'], grader.info['unix_group'])


# ----------------------------------------------------------------------------------------------------------
@task
def initialize_volumes(settings: Settings, grading_system: GradingSystem, graders: List[Grader]):
    logger = get_run_logger()

    for grader in graders:
        create_grading_volume(grader=grader)
        clone_git_repository(settings=settings, grader=grader)
        create_submission_folder(grader=grader)
        generate_assignments(grading_system=grading_system, grader=grader)
        generate_solutions(grading_system=grading_system, grader=grader)

    return graders


# ----------------------------------------------------------------------------------------------------------
@task
def initialize_accounts(grading_system: GradingSystem, graders: List[Grader]):
    logger = get_run_logger()
    users = grading_system.get_users()
    for grader in graders:
        if grader.name not in users:
            logger.info(f"User {grader.name} does not exist; creating")
            grading_system.add_grader_account(grader=grader)
    return graders

# ----------------------------------------------------------------------------------------------------------

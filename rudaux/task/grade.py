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
from rudaux.util.container import run_container
from rudaux.util.util import get_logger, recursive_chown
from rudaux.model.submission import Submission
from rudaux.model.assignment import Assignment
from rudaux.model.grader import Grader


# ----------------------------------------------------------------------------------------------------------
def _clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())


# ----------------------------------------------------------------------------------------------------------
def _grader_account_name(group_name, assignment_name, user):
    return _clean_jhub_uname(group_name) + _clean_jhub_uname(assignment_name) + _clean_jhub_uname(user)


# ----------------------------------------------------------------------------------------------------------
@task
def build_grading_team(config, course_group: str, assignment_name: str,
                       assignment_submissions_pairs: List[Tuple[Assignment, List[Submission]]]):
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
    Args = namedtuple('Args', 'directory')
    args = Args(directory=config.jupyterhub_config_dir)
    user_tuples = get_users(args)
    dictauth_users = [u[0] for u in user_tuples]
    config_users = config.assignments[course_group][assignment_name]
    graders = []

    for user in config_users:
        # ensure user exists
        if user not in dictauth_users:
            msg = f"User account {user} listed in rudaux_config does not exist in dictauth: {dictauth_users} . " \
                  f"Make sure to use dictauth to create a grader account for each of the " \
                  f"TA/instructors listed in config.assignments"
            logger.error(msg)
            raise PrefectSignal

        grader_name = _grader_account_name(course_group, assignment_name, user)
        grader_info = dict()
        # initialize any values in the grader that are *not* potential failure points here
        grader_info['user'] = user
        grader_info['assignment_name'] = assignment_name
        grader_info['name'] = _grader_account_name(course_group, assignment_name, user)
        grader_info['unix_user'] = config.jupyterhub_user
        grader_info['unix_group'] = config.jupyterhub_group
        grader_info['unix_quota'] = config.user_quota
        grader_info['folder'] = os.path.join(config.user_root, grader_info['name']).rstrip('/')
        grader_info['local_source_path'] = os.path.join('source', assignment_name, assignment_name + '.ipynb')
        grader_info['submissions_folder'] = os.path.join(grader_info['folder'], config.submissions_folder)
        grader_info['autograded_folder'] = os.path.join(grader_info['folder'], config.autograded_folder)
        grader_info['feedback_folder'] = os.path.join(grader_info['folder'], config.feedback_folder)
        grader_info['workload'] = 0  # how many submissions they have to grade
        if os.path.exists(grader_info['submissions_folder']):
            grader_info['workload'] = len([f for f in os.listdir(
                grader_info['submissions_folder']) if os.path.isdir(f)])
        grader_info['solution_name'] = assignment_name + '_solution.html'
        grader_info['solution_path'] = os.path.join(grader_info['folder'], grader_info['solution_name'])

        grader = Grader(name=grader_name, info=grader_info)
        graders.append(grader)

    return graders


# ----------------------------------------------------------------------------------------------------------
@task
def initialize_volumes(config, graders):
    logger = get_run_logger()
    for grader in graders:
        # create the zfs volume
        if not os.path.exists(grader['folder']):
            logger.info(f"Grader folder {grader['folder']} doesn't exist, creating...")
            try:
                check_output(['sudo', config.zfs_path, 'create', "-o", "refquota=" + grader['unix_quota'],
                              grader['folder'].lstrip('/')], stderr=STDOUT)
            except CalledProcessError as e:
                msg = f"Error running command {e.cmd}. return_code {e.returncode}. " \
                      f"output {e.output}. stdout {e.stdout}. stderr {e.stderr}"
                logger.error(msg)
                raise PrefectSignal
            logger.info("Created!")

        # clone the git repository
        # TODO if there's an error cloning the repo or an unknown error when doing the initial test repo create
        # email instructor and print a message to tell the user to create a deploy key
        repo_valid = False
        # allow no such path or invalid repo errors; everything else should raise
        try:
            tmprepo = git.Repo(grader['folder'])
        except git.exc.InvalidGitRepositoryError as e:
            pass
        except git.exc.NoSuchPathError as e:
            pass
        else:
            repo_valid = True
        if not repo_valid:
            logger.info(f"{grader['folder']} is not a valid course repo. "
                        f"Cloning course repository from {config.instructor_repo_url}")
            git.Repo.clone_from(config.instructor_repo_url, grader['folder'])
            logger.info("Cloned!")

        # create the submissions folder
        if not os.path.exists(grader['submissions_folder']):
            os.makedirs(grader['submissions_folder'], exist_ok=True)

        aname = grader['assignment_name']

        # reassign ownership to jupyter user
        recursive_chown(grader['folder'], grader['unix_user'], grader['unix_group'])

        # if the assignment hasn't been generated yet, generate it
        # TODO error handling if the container fails
        generated_asgns = run_container(config, 'nbgrader db assignment list', grader['folder'])
        if aname not in generated_asgns['log']:
            logger.info(f"Assignment {aname} not yet generated for grader {grader['name']}")
            output = run_container(config, 'nbgrader generate_assignment --force ' + aname, grader['folder'])
            logger.info(output['log'])
            if 'ERROR' in output['log']:
                msg = f"Error generating assignment {aname} for grader {grader['name']} at path {grader['folder']}"
                logger.error(msg)
                raise PrefectSignal

        # if the solution hasn't been generated yet, generate it
        if not os.path.exists(grader['soln_path']):
            logger.info(f"Solution for {aname} not yet generated for grader {grader['name']}")
            output = run_container(config, 'jupyter nbconvert ' + grader['local_source_path'] + ' --output=' + grader[
                'soln_name'] + ' --output-dir=.', grader['folder'])
            logger.info(output['log'])
            if 'ERROR' in output['log']:
                msg = f"Error generating solution for {aname} for grader {grader['name']} at path {grader['folder']}"
                logger.error(msg)
                raise PrefectSignal

        # transfer ownership to the jupyterhub user
        recursive_chown(grader['folder'], grader['unix_user'], grader['unix_group'])

    return graders


# ----------------------------------------------------------------------------------------------------------
@task
def initialize_accounts(config, graders):
    logger = get_run_logger()
    for grader in graders:
        # create the jupyterhub user
        Args = namedtuple('Args', 'directory')
        args = Args(directory=config.jupyterhub_config_dir)
        output = [u[0] for u in get_users(args)]
        if grader['name'] not in output:
            logger.info(f"User {grader['name']} does not exist; creating")
            Args = namedtuple('Args', 'username directory copy_creds salt digest')
            args = Args(username=grader['name'],
                        directory=config.jupyterhub_config_dir,
                        copy_creds=grader['user'],
                        salt=None,
                        digest=None)
            add_user(args)
            check_output(['systemctl', 'stop', 'jupyterhub'])
            check_output(['systemctl', 'start', 'jupyterhub'])
    return graders


# ----------------------------------------------------------------------------------------------------------


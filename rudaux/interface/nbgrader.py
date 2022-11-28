import os
from collections import namedtuple
from logging import Logger
from subprocess import check_output, CalledProcessError, STDOUT
from typing import Optional, List, Callable
from dictauth.users import add_user, remove_user, get_users
from prefect.exceptions import PrefectSignal
import git
from rudaux.interface.base.grading_system import GradingSystem
from rudaux.model import Submission
from rudaux.model.grader import Grader
from rudaux.util.container import run_container
from nbgrader.api import Gradebook, MissingEntry
from prefect import get_run_logger
from rudaux.util.util import grader_account_name, recursive_chown


def _create_submission_folder(grader: Grader):
    # create the submissions folder
    if not os.path.exists(grader.info['submissions_folder']):
        os.makedirs(grader.info['submissions_folder'], exist_ok=True)
    # reassign ownership to jupyter user
    recursive_chown(grader.info['folder'], grader.info['unix_user'], grader.info['unix_group'])


class NBGrader(GradingSystem):
    nbgrader_docker_image: str
    nbgrader_docker_memory: str
    nbgrader_docker_bind_folder: str
    nbgrader_student_folder_prefix: str
    nbgrader_instructor_user: str
    nbgrader_jupyterhub_config_dir: str
    nbgrader_jupyterhub_user: str
    nbgrader_user_quota: str
    nbgrader_user_root: str
    nbgrader_submissions_folder: Optional[str] = 'submitted'
    nbgrader_feedback_folder: Optional[str] = 'feedback'
    nbgrader_autograded_folder: Optional[str] = 'autograded'
    instructor_repo_url: str
    zfs_path: Optional[str] = "/usr/sbin/zfs"

    # -----------------------------------------------------------------------------------------
    def open(self):
        pass

    # -----------------------------------------------------------------------------------------
    def close(self):
        pass

    # -----------------------------------------------------------------------------------------
    def initialize(self):
        self.users = self.get_users()

    # -----------------------------------------------------------------------------------------
    def _get_generated_assignments(self, work_dir: str) -> dict:
        generated_assignments = run_container(
            command='nbgrader db assignment list', docker_image=self.nbgrader_docker_image,
            docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)
        return generated_assignments

    # -----------------------------------------------------------------------------------------
    def generate_assignment(self, grader: Grader):
        """
        generates the grader's assignment if it has not been generated before

        Parameters
        ----------
        grader: Grader

        Returns
        -------

        """

        logger = get_run_logger()

        assignment_name = grader.info['assignment_name']
        work_dir = grader.info['folder']
        grader_name = grader.info['name']

        # if the assignment hasn't been generated yet, generate it
        generated_assignments = self._get_generated_assignments(work_dir=work_dir)

        if assignment_name not in generated_assignments['log']:
            logger.info(f"Assignment {assignment_name} not yet generated for grader {grader_name}")

            output = run_container(
                command=f"nbgrader generate_assignment --force {assignment_name}",
                docker_image=self.nbgrader_docker_image,
                docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

            logger.info(output['log'])

            if 'ERROR' in output['log']:
                msg = f"Error generating assignment {assignment_name} for grader " \
                      f"{grader.info['name']} at path {work_dir}"
                logger.error(msg)
                raise PrefectSignal

    # -----------------------------------------------------------------------------------------
    def generate_solution(self, grader: Grader):

        """
        generates the solution for the grader's assignment if it has not been generated before

        Parameters
        ----------
        grader: Grader

        Returns
        -------

        """

        logger = get_run_logger()
        assignment_name = grader.info['assignment_name']
        local_source_path = grader.info['local_source_path']
        solution_name = grader.info['solution_name']
        work_dir = grader.info['folder']

        # if the solution hasn't been generated yet, generate it
        if not os.path.exists(grader.info['solution_path']):
            logger.info(f"Solution for {assignment_name} not yet generated for grader {grader.info['name']}")

            command = f"jupyter nbconvert {local_source_path} --output={solution_name} --output-dir=."
            output = run_container(
                command=command, docker_image=self.nbgrader_docker_image,
                docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

            logger.info(output['log'])

            if 'ERROR' in output['log']:
                msg = f"Error generating solution for {assignment_name} for grader " \
                      f"{grader.info['name']} at path {grader.info['folder']}"
                logger.error(msg)
                raise PrefectSignal

        # transfer ownership to the jupyterhub user
        recursive_chown(grader.info['folder'], grader.info['unix_user'], grader.info['unix_group'])

    # -----------------------------------------------------------------------------------------
    def generate_feedback(self, submission: Submission, work_dir: str):

        command = f"nbgrader generate_feedback " \
                  f"--force " \
                  f"--assignment={submission.assignment.name} " \
                  f"--student={self.nbgrader_student_folder_prefix}{submission.student.lms_id}"

        output = run_container(command=command, docker_image=self.nbgrader_docker_image,
                               docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------
    def get_needs_manual_grading(self, work_dir: str):
        pass

    # -----------------------------------------------------------------------------------------
    def autograde(self, submission: Submission, work_dir: str):
        logger = get_run_logger()
        logger.info(f"Autograding submission {submission.lms_id}")
        logger.info('Removing old autograding result from DB if it exists')
        try:
            gb = Gradebook('sqlite:///' + os.path.join(work_dir, 'gradebook.db'))
            gb.remove_submission(submission.assignment.name,
                                 self.nbgrader_student_folder_prefix + submission.student.lms_id)
        except MissingEntry as e:
            pass
        else:
            gb.close()

        logger.info('Autograding...')

        command = f"nbgrader autograde " \
                  f"--force " \
                  f"--assignment={submission.assignment.name} " \
                  f"--student={self.nbgrader_student_folder_prefix}{submission.student.lms_id}"

        output = run_container(command=command, docker_image=self.nbgrader_docker_image,
                               docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------
    def build_grader(self, course_name: str, assignment_name: str, username: str, skip: bool) -> Grader:
        grader_name = grader_account_name(course_name, assignment_name, username)
        info = dict()
        info['user'] = username
        info['name'] = grader_name
        info['assignment_name'] = assignment_name
        info['unix_user'] = self.nbgrader_jupyterhub_user
        info['unix_group'] = self.nbgrader_user_quota
        info['folder'] = os.path.join(self.nbgrader_user_root, grader_name).rstrip('/')
        info['local_source_path'] = os.path.join('source', assignment_name, assignment_name + '.ipynb')
        info['submissions_folder'] = os.path.join(info['folder'], self.nbgrader_submissions_folder)
        info['autograded_folder'] = os.path.join(info['folder'], self.nbgrader_autograded_folder)
        info['feedback_folder'] = os.path.join(info['folder'], self.nbgrader_feedback_folder)
        info['workload'] = 0  # how many submissions they have to grade
        if os.path.exists(info['submissions_folder']):
            info['workload'] = len([f for f in os.listdir(info['submissions_folder']) if os.path.isdir(f)])
        info['solution_name'] = assignment_name + '_solution.html'
        info['solution_path'] = os.path.join(info['folder'], info['solution_name'])

        grader = Grader(name=grader_name, info=info, skip=skip)
        return grader

    # -----------------------------------------------------------------------------------------
    def get_users(self) -> List[str]:
        # get list of users from dictauth
        Args = namedtuple('Args', 'directory')
        args = Args(directory=self.nbgrader_jupyterhub_config_dir)
        user_tuples = get_users(args)
        dictauth_users = [u[0] for u in user_tuples]
        return dictauth_users

    # -----------------------------------------------------------------------------------------
    def _add_grader_account(self, grader: Grader):
        # create the jupyterhub user
        Args = namedtuple('Args', 'username directory copy_creds salt digest')
        args = Args(username=grader.name,
                    directory=self.nbgrader_jupyterhub_config_dir,
                    copy_creds=grader.info['user'],
                    salt=None,
                    digest=None)
        add_user(args)
        check_output(['systemctl', 'stop', 'jupyterhub'])
        check_output(['systemctl', 'start', 'jupyterhub'])

    # -----------------------------------------------------------------------------------------
    def _create_grading_volume(self, grader: Grader):
        logger = get_run_logger()
        # create the zfs volume
        if not os.path.exists(grader.info['folder']):
            logger.info(f"Grader folder {grader.info['folder']} doesn't exist, creating...")
            try:
                # zfs_path = "/usr/sbin/zfs"
                check_output(['sudo', self.zfs_path, 'create', "-o", "refquota=" + grader.info['unix_quota'],
                              grader.info['folder'].lstrip('/')], stderr=STDOUT)
            except CalledProcessError as e:
                msg = f"Error running command {e.cmd}. return_code {e.returncode}. " \
                      f"output {e.output}. stdout {e.stdout}. stderr {e.stderr}"
                logger.error(msg)
                raise PrefectSignal
            logger.info("Created!")

    # ----------------------------------------------------------------------------------------------------------
    def _clone_git_repository(self, grader: Grader):
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
                        f"Cloning course repository from {self.instructor_repo_url}")
            git.Repo.clone_from(self.instructor_repo_url, grader.info['folder'])
            logger.info("Cloned!")

    # ----------------------------------------------------------------------------------------------------------
    def _initialize_account(self, grader: Grader):
        """
        create grader jhub account

        Parameters
        ----------
        grader: Grader

        Returns
        -------
        grader: Grader
        """

        logger = get_run_logger()
        # users = self.get_users()
        if grader.name not in self.users:
            logger.info(f"User {grader.name} does not exist; creating")
            self._add_grader_account(grader=grader)
        return grader
    # ----------------------------------------------------------------------------------------------------------

    def initialize_grader(self, grader: Grader):
        """
        create grader volumes, add git repos, create folder structures, initialize nbgrader

        Parameters
        ----------
        grader: Grader

        Returns
        -------
        grader: Grader
        """

        self._create_grading_volume(grader=grader)
        self._clone_git_repository(grader=grader)
        _create_submission_folder(grader=grader)
        self.generate_assignment(grader=grader)
        self.generate_solution(grader=grader)
        self._initialize_account(grader=grader)

        return grader


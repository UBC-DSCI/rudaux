import os
from collections import namedtuple
from logging import Logger
from subprocess import check_output
from typing import Optional, List, Callable
from dictauth.users import add_user, remove_user, get_users
from rudaux.interface.base.grading_system import GradingSystem
from rudaux.model import Submission
from rudaux.model.grader import Grader
from rudaux.util.container import run_container
from nbgrader.api import Gradebook, MissingEntry
from prefect import get_run_logger

from rudaux.util.util import grader_account_name


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

    # -----------------------------------------------------------------------------------------
    def open(self):
        pass

    # -----------------------------------------------------------------------------------------
    def close(self):
        pass

    # -----------------------------------------------------------------------------------------
    def initialize(self):
        pass

    # -----------------------------------------------------------------------------------------
    def get_generated_assignments(self, work_dir: str) -> dict:
        generated_assignments = run_container(
            command='nbgrader db assignment list', docker_image=self.nbgrader_docker_image,
            docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)
        return generated_assignments

    # -----------------------------------------------------------------------------------------
    def generate_assignment(self, assignment_name: str, work_dir: str):
        # logger = get_run_logger()
        # generated_assignments = run_container(
        #     command='nbgrader db assignment list', docker_image=self.nbgrader_docker_image,
        #     docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)
        #
        # if assignment_name not in generated_assignments['log']:
        #     logger.info(f"Assignment {assignment_name} not yet generated for grader {work_dir}")
        #     output = run_container(
        #         command=f"nbgrader generate_assignment --force {assignment_name}",
        #         docker_image=self.nbgrader_docker_image,
        #         docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

        output = run_container(
            command=f"nbgrader generate_assignment --force {assignment_name}",
            docker_image=self.nbgrader_docker_image,
            docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------
    def generate_solution(self, local_source_path: str, solution_name: str, work_dir: str):
        # nbgrader generate_solution
        command = f"jupyter nbconvert {local_source_path} --output={solution_name} --output-dir=."
        output = run_container(
            command=command, docker_image=self.nbgrader_docker_image,
            docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

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
    def build_grader(self, course_name: str, assignment_name: str, username: str) -> Grader:
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

        grader = Grader(name=grader_name, info=info)
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
    def add_grader_account(self, grader: Grader):
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
    def initialize_grader_volumes(self, logger: Logger, grader: Grader, function: Callable[[str, str], any]):
        # create the zfs volume
        if not os.path.exists(grader.info['folder']):
            logger.info(f"Grader folder {grader.info['folder']} doesn't exist, creating...")
            function(grader.info['unix_quota'], grader.info['folder'].lstrip('/'))
            logger.info("Created!")

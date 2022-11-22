import os
from rudaux.interface.base.grading_system import GradingSystem
from rudaux.model import Submission
from rudaux.util.container import run_container
from nbgrader.api import Gradebook, MissingEntry
from prefect import get_run_logger


class NBGrader(GradingSystem):
    docker_image: str
    docker_memory: str
    grading_student_folder_prefix: str

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
    def generate_assignment(self, assignment_name: str, work_dir: str):
        logger = get_run_logger()
        generated_assignments = run_container(
            command='nbgrader db assignment list', docker_image=self.docker_image,
            docker_memory=self.docker_memory, work_dir=work_dir)

        if assignment_name not in generated_assignments['log']:
            logger.info(f"Assignment {assignment_name} not yet generated for grader {work_dir}")
            output = run_container(
                command=f"nbgrader generate_assignment --force {assignment_name}",
                docker_image=self.docker_image,
                docker_memory=self.docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------
    def generate_solution(self, local_source_path: str, solution_name: str, work_dir: str):
        # nbgrader generate_solution
        command = f"jupyter nbconvert {local_source_path} --output={solution_name} --output-dir=."
        output = run_container(
            command=command, docker_image=self.docker_image,
            docker_memory=self.docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------
    def generate_feedback(self, submission: Submission, work_dir: str):

        command = f"nbgrader generate_feedback " \
                  f"--force " \
                  f"--assignment={submission.assignment.name} " \
                  f"--student={self.grading_student_folder_prefix}{submission.student.lms_id}"

        output = run_container(command=command, docker_image=self.docker_image,
                               docker_memory=self.docker_memory, work_dir=work_dir)

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
                                 self.grading_student_folder_prefix + submission.student.lms_id)
        except MissingEntry as e:
            pass
        else:
            gb.close()

        logger.info('Autograding...')

        command = f"nbgrader autograde " \
                  f"--force " \
                  f"--assignment={submission.assignment.name} " \
                  f"--student={self.grading_student_folder_prefix}{submission.student.lms_id}"

        output = run_container(command=command, docker_image=self.docker_image,
                               docker_memory=self.docker_memory, work_dir=work_dir)

    # -----------------------------------------------------------------------------------------

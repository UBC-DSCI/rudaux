import json
import os
import shutil
from collections import namedtuple
from json import JSONDecodeError
from logging import Logger
from subprocess import check_output, CalledProcessError, STDOUT
from typing import Optional, List, Callable
import pendulum as plm
from bs4 import BeautifulSoup
from dictauth.users import add_user, remove_user, get_users
from prefect.exceptions import PrefectSignal
import git
from rudaux.interface.base.grading_system import GradingSystem, GradingStatus
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


def _compute_max_score(submission: Submission):
    # for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything
    # (so we cannot easily convert scores to percentages)
    # let's compute the max_score from the notebook manually then....
    release_nb_path = os.path.join(
        submission.grader.info['folder'], 'release',
        submission.assignment.name, submission.assignment.name + '.ipynb')
    f = open(release_nb_path, 'r')
    parsed_json = json.load(f)
    f.close()
    pts = 0
    for cell in parsed_json['cells']:
        try:
            pts += cell['metadata']['nbgrader']['points']
        except Exception as e:
            # will throw exception if cells don't exist / not right type -- that's fine, it'll happen a lot.
            print(e)
            pass
    return pts


class NBGrader(GradingSystem):
    nbgrader_docker_image: str
    nbgrader_docker_memory: str
    nbgrader_docker_bind_folder: str
    nbgrader_student_folder_prefix: str
    nbgrader_instructor_user: str
    nbgrader_jupyterhub_config_dir: str
    nbgrader_jupyterhub_user: str
    nbgrader_jupyterhub_group: str
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
        # get list of users from dictauth
        self.users = self._get_users()

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
        recursive_chown(grader.info['folder'],
                        self.nbgrader_jupyterhub_user,
                        self.nbgrader_jupyterhub_group)

    # -----------------------------------------------------------------------------------------
    def generate_feedback(self, submission: Submission):

        logger = get_run_logger()

        grader = submission.grader
        student = submission.student
        assignment = submission.assignment
        work_dir = grader.info['folder']

        if grader.status == GradingStatus.NOT_DUE or \
                grader.status == GradingStatus.MISSING or \
                os.path.exists(grader.info['generated_feedback_path']):
            return
        logger.info(f"Generating feedback for submission {submission.lms_id}")

        attempts = 3
        for attempt in range(attempts):
            command = f"nbgrader generate_feedback " \
                      f"--force " \
                      f"--assignment={submission.assignment.name} " \
                      f"--student={self.nbgrader_student_folder_prefix}{submission.student.lms_id}"

            output = run_container(command=command, docker_image=self.nbgrader_docker_image,
                                   docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

            if not os.path.exists(grader.info['generated_feedback_path']):
                logger.info(
                    f"Docker error generating feedback for submission {submission.lms_id}: "
                    f"did not generate expected file at {grader.info['generated_feedback_path']}")
                if attempt < attempts - 1:
                    logger.info("Trying again...")
                    continue
                else:
                    msg = f"Docker error generating feedback for submission {submission.lms_id}: " \
                          f"did not generate expected file at {grader.info['generated_feedback_path']}"
                    logger.error(msg)
                    raise PrefectSignal

            # open the feedback form that was just generated and make sure the final grade lines up with the DB grade

            # STEP 1: load grades from feedback form
            # (and check internal consistency with totals and individual grade cells)
            # the final grade and TOC on the form looks like
            # <div class="panel-heading">
            # <h4>tutorial_wrangling (Score: 35.0 / 44.0)</h4>
            # <div id="toc">
            # <ol>
            # <li><a href="#cell-b2ed899f3e35cfcb">Test cell</a> (Score: 1.0 / 1.0)</li>
            # ...
            # </ol>
            fdbk_html = None
            with open(grader.info['generated_feedback_path'], 'r') as f:
                fdbk_html = f.read()
            fdbk_parsed = BeautifulSoup(fdbk_html, features="lxml")
            cell_tokens_bk = []
            cell_score_bk = []
            total_tokens = [s.strip(")(") for s in
                            fdbk_parsed.body.find('div', {"id": "toc"}).find_previous_sibling('h4').text.split()]
            total = [float(total_tokens[i]) for i in [-3, -1]]
            running_totals = [0.0, 0.0]
            for item in fdbk_parsed.body.find('div', {"id": "toc"}).find('ol').findAll('li'):
                if "Comment" in item.text:
                    continue
                cell_tokens = [s.strip(")(") for s in item.text.split()]
                cell_tokens_bk.append(cell_tokens)
                cell_score = [float(cell_tokens[i]) for i in [-3, -1]]
                cell_score_bk.append(cell_score)
                running_totals[0] += cell_score[0]
                running_totals[1] += cell_score[1]

            # if sum of grades doesn't equal total grade, error
            if abs(running_totals[0] - total[0]) > 1e-5:
                logger.info(
                    f"Docker error generating feedback for submission {submission.lms_id}: "
                    f"grade does not line up within feedback file!")
                logger.info(
                    f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  "
                    f"running_totals[1]: {running_totals[1]} total[1]: {total[1]}")
                logger.info(f"Docker container log: \n {output['log']}")
                logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n "
                            f"Cell Tokens: \n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                logger.info(f"HTML for total:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find_previous_sibling('h4').text}")
                logger.info(f"HTML for individual:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find('ol').findAll('li')}")
                if attempt < attempts - 1:
                    logger.info("Trying again...")
                    continue
                else:
                    msg = f"Docker error generating feedback for submission {submission.lms_id}: " \
                          f"grade does not line up within feedback file!"
                    os.remove(grader.info['generated_feedback_path'])
                    logger.error(msg)
                    raise PrefectSignal

            # if assignment max doesn't equal sum of question maxes,
            # warning; this can occur if student deleted test cell
            if abs(running_totals[1] - total[1]) > 1e-5:
                logger.info(
                    f"Docker warning generating feedback for submission {submission.lms_id}: "
                    f"total grade does not line up within feedback file (likely due to deleted grade cell)!")
                logger.info(f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  "
                            f"running_totals[1]: {running_totals[1]} total[1]: {total[1]}")
                logger.info(f"Docker container log: \n {output['log']}")
                logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n Cell Tokens: "
                            f"\n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                logger.info(f"HTML for total:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find_previous_sibling('h4').text}")
                logger.info(f"HTML for individual:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find('ol').findAll('li')}")

            # STEP 2: load grades from gradebook and compare
            student = submission.student
            try:
                gb = Gradebook('sqlite:///' + os.path.join(work_dir, 'gradebook.db'))
                gb_submission = gb.find_submission(
                    assignment.name, self.nbgrader_student_folder_prefix + student.lms_id)
                score = gb_submission.score
            except Exception as e:
                msg = f"Error when accessing the gradebook score for submission " \
                      f"{submission.lms_id}; error {str(e)}"
                os.remove(grader.info['generated_feedback_path'])
                logger.error(msg)
                raise PrefectSignal
            else:
                gb.close()

            # if feedback grade != canvas grade, error
            if abs(total[0] - score) > 1e-5:
                logger.info(
                    f"Docker error generating feedback for submission {submission.lms_id}: "
                    f"grade does not line up with DB!")
                logger.info(
                    f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  running_totals[1]: "
                    f"{running_totals[1]} total[1]: {total[1]} score: {score}")
                logger.info(f"Docker container log: \n {output['log']}")
                logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n Cell Tokens: "
                            f"\n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                logger.info(f"HTML for total:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find_previous_sibling('h4').text}")
                logger.info(f"HTML for individual:\n "
                            f"{fdbk_parsed.body.find('div', {'id': 'toc'}).find('ol').findAll('li')}")
                logger.info(f"DB score: {score}")
                if attempt < attempts - 1:
                    logger.info("Trying again...")
                    continue
                else:
                    msg = f"Docker error generating feedback for submission {submission.lms_id}: " \
                          f"grade does not line up with DB!; docker container log: \n {output['log']}"
                    os.remove(grader.info['generated_feedback_path'])
                    logger.error(msg)
                    raise PrefectSignal
            break

    # -----------------------------------------------------------------------------------------
    def get_needs_manual_grading(self, submission: Submission):

        logger = get_run_logger()

        grader = submission.grader
        student = submission.student
        assignment = submission.assignment
        work_dir = grader.info['folder']

        # check if the submission needs manual grading
        try:
            gb = Gradebook('sqlite:///' + os.path.join(work_dir, 'gradebook.db'))
            gb_submission = gb.find_submission(assignment.name, self.nbgrader_student_folder_prefix + student.lms_id)
            flag = gb_submission.needs_manual_grade
        except Exception as e:
            msg = f"Error when checking whether submission {submission.lms_id} needs manual grading; error {str(e)}"
            logger.error(msg)
            raise PrefectSignal
        else:
            gb.close()

        # if the need manual grade flag is set, and we don't find the IGNORE_MANUAL_GRADING file
        # this is a hack to deal with the fact that sometimes nbgrader
        # just thinks an assignment needs manual grading
        # even when it doesn't, and there's nothing the TA can do to convince it otherwise.
        # when that happens, we just touch IGNORE_MANUAL_GRADING inside the folder
        if flag and not os.path.exists(os.path.join(work_dir, 'IGNORE_MANUAL_GRADING')):
            grader.status = GradingStatus.NEEDS_MANUAL_GRADE
        else:
            grader.status = GradingStatus.DONE_GRADING

    # -----------------------------------------------------------------------------------------
    def autograde(self, submission: Submission):

        logger = get_run_logger()

        grader = submission.grader
        student = submission.student
        assignment = submission.assignment
        work_dir = grader.info['folder']

        if os.path.exists(grader.info['autograded_assignment_path']):
            grader.status = GradingStatus.AUTOGRADED
            return

        logger.info(f"Autograding submission {submission.lms_id}")
        logger.info('Removing old autograding result from DB if it exists')

        try:
            gb = Gradebook('sqlite:///' + os.path.join(work_dir, 'gradebook.db'))
            gb.remove_submission(assignment.name, self.nbgrader_student_folder_prefix + student.lms_id)
        except MissingEntry as e:
            pass
        else:
            gb.close()

        logger.info('Autograding...')
        command = f"nbgrader autograde " \
                  f"--force " \
                  f"--assignment={assignment.name} " \
                  f"--student={self.nbgrader_student_folder_prefix}{student.lms_id}"

        output = run_container(command=command, docker_image=self.nbgrader_docker_image,
                               docker_memory=self.nbgrader_docker_memory, work_dir=work_dir)

        # validate the results
        if 'ERROR' in output['log']:
            logger.warning(
                f"Docker error autograding submission {submission.lms_id}: "
                f"exited with status {output['exit_status']},  {output['log']}")
            logger.warning(f"May still continue if rudaux determines this error is nonfatal")

        # as long as we generate a file, assume success
        # (avoids weird errors that don't actually cause a problem killing rudaux)
        if not os.path.exists(grader.info['autograded_assignment_path']):
            msg = f"Docker error autograding submission {submission.lms_id}: " \
                  f"did not generate expected file at {grader.info['autograded_assignment_path']}"
            logger.error(msg)
            raise PrefectSignal

        grader.status = GradingStatus.AUTOGRADED

    # -----------------------------------------------------------------------------------------
    def build_grader(self, course_name: str, assignment_name: str, username: str, skip: bool) -> Grader:
        """
        builds the grader object by adding required info

        Parameters
        ----------
        course_name: str
        assignment_name: str
        username: str
        skip: bool

        Returns
        -------
        grader: Grader

        """

        logger = get_run_logger()

        # users = self.get_users()
        # ensure user exists
        if username not in self.users:
            msg = f"User account {username} listed in rudaux_config does not exist in dictauth: {self.users} . " \
                  f"Make sure to use dictauth to create a grader account for each of the " \
                  f"TA/instructors listed in config.assignments"
            logger.error(msg)
            raise PrefectSignal

        grader_name = grader_account_name(course_name, assignment_name, username)
        info = dict()
        info['user'] = username
        info['name'] = grader_name
        info['assignment_name'] = assignment_name
        info['unix_user'] = self.nbgrader_jupyterhub_user
        info['unix_group'] = self.nbgrader_jupyterhub_group
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

        status = GradingStatus.NOT_ASSIGNED
        grader = Grader(name=grader_name, info=info, status=status, skip=skip)
        return grader

    # -----------------------------------------------------------------------------------------
    def _get_users(self) -> List[str]:
        """
        get list of users from dictauth

        Returns
        -------
        dictauth_users: List[str]
        """

        Args = namedtuple('Args', 'directory')
        args = Args(directory=self.nbgrader_jupyterhub_config_dir)
        user_tuples = get_users(args)
        dictauth_users = [u[0] for u in user_tuples]
        return dictauth_users

    # -----------------------------------------------------------------------------------------
    def _add_grader_account(self, grader: Grader):
        """
        create the jupyterhub user

        Parameters
        ----------
        grader: Grader

        Returns
        -------
        """

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
        """
        creates the zfs volume and sets the refquota for grader if the volume does not already exist

        Parameters
        ----------
        grader: Grader

        Returns
        -------
        """

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
        """
        clones the instructor repo into the grader's volume

        Parameters
        ----------
        grader: Grader

        Returns
        -------
        """

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
        # users = self._get_users()
        if grader.name not in self.users:
            logger.info(f"User {grader.name} does not exist; creating")
            self._add_grader_account(grader=grader)
        return grader

    # ----------------------------------------------------------------------------------------------------------
    def initialize_grader(self, grader: Grader) -> Grader:
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

    # ----------------------------------------------------------------------------------------------------------
    def assign_submission_to_grader(self, graders: List[Grader], submission: Submission):

        student = submission.student
        assignment_name = submission.assignment.name
        found = False

        for grader in graders:
            collected_assignment_folder = os.path.join(
                grader.info['submissions_folder'], self.nbgrader_student_folder_prefix + student.lms_id)
            if os.path.exists(collected_assignment_folder):
                found = True
                submission.grader = grader
                break

        # if not assigned to anyone, choose the worker with the minimum current workload
        if not found:
            # sort graders in place and assign
            graders.sort(key=lambda g: g['workload'])
            min_grader = graders[0]
            min_grader.info['workload'] += 1
            submission.grader = min_grader

        # fill in the submission details that depend on a grader
        submission.grader.info['collected_assignment_folder'] = os.path.join(
            submission.grader.info['submissions_folder'],
            self.nbgrader_student_folder_prefix + student.lms_id)

        submission.grader.info['collected_assignment_path'] = os.path.join(
            submission.grader.info['submissions_folder'],
            self.nbgrader_student_folder_prefix + student.lms_id,
            assignment_name, assignment_name + '.ipynb')

        submission.grader.info['autograded_assignment_path'] = os.path.join(
            submission.grader.info['autograded_folder'],
            self.nbgrader_student_folder_prefix + student.lms_id,
            assignment_name, assignment_name + '.ipynb')

        submission.grader.info['generated_feedback_path'] = os.path.join(
            submission.grader.info['feedback_folder'],
            self.nbgrader_student_folder_prefix + student.lms_id,
            assignment_name, assignment_name + '.html')

    # ----------------------------------------------------------------------------------------------------------
    def collect_grader_submissions(self, submission: Submission):
        logger = get_run_logger()
        grader = submission.grader
        if not os.path.exists(grader.info['collected_assignment_path']):
            if not os.path.exists(grader.info['snapped_assignment_path']):
                grader.status = GradingStatus.MISSING
            else:
                logger.info(f"Submission {submission.lms_id} not yet collected. Collecting...")
                os.makedirs(os.path.dirname(grader.info['collected_assignment_path']), exist_ok=True)

                shutil.copy(grader.info['snapped_assignment_path'],
                            grader.info['collected_assignment_path'])

                recursive_chown(grader.info['collected_assignment_folder'],
                                self.nbgrader_jupyterhub_user,
                                self.nbgrader_jupyterhub_group)

                grader.status = GradingStatus.COLLECTED
        else:
            grader.status = GradingStatus.COLLECTED

    # ----------------------------------------------------------------------------------------------------------
    def clean_grader_submission(self, submission: Submission):

        logger = get_run_logger()

        # need to check for duplicate cell ids, see
        # https://github.com/jupyter/nbgrader/issues/1083

        # need to make sure the cell_type agrees with nbgrader cell_type
        # (students accidentally sometimes change it)

        grader = submission.grader
        student = submission.student
        assignment = submission.assignment
        course_name = submission.course_section_info.name

        # open the student's notebook
        try:
            collected_assignment_path = grader.info['collected_assignment_path']
            f = open(collected_assignment_path, 'r')
            nb = json.load(f)
            f.close()

        except JSONDecodeError as e:
            msg = (f"JSON ERROR in student {student.name} {student.lms_id} assignment {assignment.name} "
                   f"grader {grader.name} course name {course_name}" +
                   "This can happen if cleaning was previously abruptly stopped, leading to a corrupted file." +
                   "It might also happen if the student somehow deleted "
                   "their file and left a non-JSON file behind." +
                   "Either way, this workflow will fail now to prevent further damage; "
                   "please inspect the file and fix the issue" +
                   "(typically by manually re-copying the student work into the grader/submitted folder")

            logger.error(msg)
            raise PrefectSignal

        # go through and
        # 1) make sure cell type agrees with nbgrader cell type
        # 2) delete the nbgrader metadata from any duplicated cells
        cell_ids = set()
        for cell in nb['cells']:
            # align cell-type with nbgrader cell-type
            try:
                cell_id = cell['metadata']['nbgrader']['grade_id']
                # ensure cell has both types by trying to read them
                cell_type = cell['cell_type']
                nbgrader_cell_type = cell['metadata']['nbgrader']['cell_type']
                if cell_type != nbgrader_cell_type:
                    logger.info(
                        f"Student {student.name} assignment {assignment.name} grader {grader.name} "
                        f"had incorrect cell type, {cell_type} != {nbgrader_cell_type}, cell ID = {cell_id}")
                    logger.info(f"Setting cell type to {nbgrader_cell_type} to avoid bugs in autograde")
                    # make cell_type align
                    cell['cell_type'] = nbgrader_cell_type
            except Exception as e:
                print(e)
                pass

            try:
                # ensure execution count exists for code cells, and does not exist for markdown cells
                # ensure no outputs for markdown cells
                cell_type = cell['cell_type']
                if cell_type == 'markdown':
                    cell.pop("execution_count", None)
                    cell.pop("outputs", None)
                if cell_type == 'code' and "execution_count" not in cell:
                    cell["execution_count"] = None
            except Exception as e:
                print(e)
                pass

            # delete nbgrader metadata from duplicated cells
            try:
                cell_id = cell['metadata']['nbgrader']['grade_id']
            except Exception as e:
                print(e)
                continue

            if cell_id in cell_ids:
                logger.info(
                    f"Student {student.name} assignment {assignment.name} grader "
                    f"{grader.name} had a duplicate cell! ID = {cell_id}")
                logger.info("Removing the nbgrader meta-info from that cell to avoid bugs in autograde")
                cell['metadata'].pop('nbgrader', None)
            else:
                cell_ids.add(cell_id)

        # write the sanitized notebook back to the submitted folder
        f = open(collected_assignment_path, 'w')
        json.dump(nb, f)
        f.close()

        grader.status = GradingStatus.PREPARED

    # ----------------------------------------------------------------------------------------------------------
    def return_feedback(self, submission: Submission):

        logger = get_run_logger()

        student = submission.student
        assignment = submission.assignment
        grader = submission.grader

        # logger.info(f"Checking whether feedback for submission {submission.lms_id} can be returned")
        if assignment.due_at < plm.now() and grader.status != GradingStatus.MISSING:
            if not os.path.exists(grader.info['generated_feedback_path']):
                logger.warning(f"Warning: feedback file {grader.info['generated_feedback_path']} "
                               f"doesnt exist yet. Skipping feedback return.")
                return
            if not os.path.exists(grader.info['fdbk_path']):
                logger.info(f"Returning feedback for submission {submission.lms_id}")
                if os.path.exists(grader.info['student_folder']):
                    shutil.copy(grader.info['generated_feedback_path'], grader.info['fdbk_path'])

                    recursive_chown(grader.info['fdbk_path'],
                                    self.nbgrader_jupyterhub_user,
                                    self.nbgrader_jupyterhub_group)
                else:
                    logger.warning(f"Warning: student folder {grader.info['student_folder']} "
                                   f"doesnt exist. Skipping feedback return.")

    # ----------------------------------------------------------------------------------------------------------
    def compute_submission_percent_grade(self, submission: Submission) -> str:

        logger = get_run_logger()

        student = submission.student
        assignment = submission.assignment
        grader = submission.grader
        work_dir = grader.info['folder']

        logger.info(f"Uploading grade for submission {submission.lms_id}")
        logger.info(f"Obtaining score from the gradebook")
        try:
            gb = Gradebook('sqlite:///' + os.path.join(work_dir, 'gradebook.db'))
            gb_submission = gb.find_submission(
                assignment.name, self.nbgrader_student_folder_prefix + student.lms_id)
            score = gb_submission.score
        except Exception as e:
            msg = f"Error when accessing the gradebook score for submission {submission.lms_id}; error {str(e)}"
            logger.error(msg)
            raise PrefectSignal
        else:
            gb.close()

        logger.info(f"Score: {score}")

        logger.info(f"Computing the max score from the release notebook")
        try:
            max_score = _compute_max_score(submission=submission)
        except Exception as e:
            msg = f"Error when trying to compute the max score for submission {submission.lms_id}; error {str(e)}"
            logger.error(msg)
            raise PrefectSignal
        logger.info(f"Max Score: {max_score}")

        # pct = "{:.2f}".format(100 * score / max_score)
        pct = round(100 * score / max_score, 2)
        logger.info(f"Percent grade: {pct}")

        return pct
    # ----------------------------------------------------------------------------------------------------------




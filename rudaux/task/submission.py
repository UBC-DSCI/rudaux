import json
import shutil
from enum import IntEnum
from json import JSONDecodeError
from typing import List

from prefect.exceptions import PrefectSignal
import os
from prefect import task, get_run_logger
import pendulum as plm
from rudaux.util.util import recursive_chown
from rudaux.model.submission import Submission
from rudaux.model.assignment import Assignment


class GradingStatus(IntEnum):
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    AUTOGRADED = 6
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10


# ----------------------------------------------------------------------------------------------------------
@task
def assign_graders(config, subm_set, graders):
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']
        tz = course_info['time_zone']
        for subm in subm_set[course_name]['submissions']:
            student = subm['student']

            # search for this student in the grader folders
            found = False
            for grader in graders:
                collected_assignment_folder = os.path.join(grader['submissions_folder'],
                                                           config.grading_student_folder_prefix + student['id'])
                if os.path.exists(collected_assignment_folder):
                    found = True
                    subm['grader'] = grader
                    break
            # if not assigned to anyone, choose the worker with the minimum current workload
            if not found:
                # sort graders in place and assign
                graders.sort(key=lambda g: g['workload'])
                min_grader = graders[0]
                min_grader['workload'] += 1
                subm['grader'] = min_grader

            # fill in the submission details that depend on a grader
            subm['collected_assignment_folder'] = os.path.join(subm['grader']['submissions_folder'],
                                                               config.grading_student_folder_prefix + student['id'])
            subm['collected_assignment_path'] = os.path.join(subm['grader']['submissions_folder'],
                                                             config.grading_student_folder_prefix + student['id'],
                                                             assignment['name'], assignment['name'] + '.ipynb')
            subm['autograded_assignment_path'] = os.path.join(subm['grader']['autograded_folder'],
                                                              config.grading_student_folder_prefix + student['id'],
                                                              assignment['name'], assignment['name'] + '.ipynb')
            subm['generated_feedback_path'] = os.path.join(subm['grader']['feedback_folder'],
                                                           config.grading_student_folder_prefix + student['id'],
                                                           assignment['name'], assignment['name'] + '.html')
            subm['status'] = GradingStatus.ASSIGNED
    return subm_set


# ----------------------------------------------------------------------------------------------------------
@task
def collect_submissions(config, subm_set, lms):
    logger = get_run_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        course_info = subm_set[course_name]['course_info']
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            student = subm['student']

            # if the submission is due in the future, skip
            if subm['due_at'] > plm.now():
                subm['status'] = GradingStatus.NOT_DUE
                continue

            if not os.path.exists(subm['collected_assignment_path']):
                if not os.path.exists(subm['snapped_assignment_path']):
                    subm['status'] = GradingStatus.MISSING
                    if subm['score'] is None:
                        logger.info(f"Submission {subm['name']} is missing. Uploading score of 0.")
                        subm['score'] = 0.
                        put_grade(config, course_info['id'], student, assignment, subm['score'])
                        lms.update_grade()
                else:
                    logger.info(f"Submission {subm['name']} not yet collected. Collecting...")
                    os.makedirs(os.path.dirname(subm['collected_assignment_path']), exist_ok=True)
                    shutil.copy(subm['snapped_assignment_path'], subm['collected_assignment_path'])
                    recursive_chown(subm['collected_assignment_folder'], subm['grader']['unix_user'],
                                    subm['grader']['unix_group'])
                    subm['status'] = GradingStatus.COLLECTED
            else:
                subm['status'] = GradingStatus.COLLECTED
    return subm_set


# ----------------------------------------------------------------------------------------------------------
@task
def clean_submissions(assignment: Assignment, submissions: List[Submission]):
    logger = get_run_logger()

    for submission in submissions:
        if subm['status'] == GradingStatus.COLLECTED:
            student = submission.student
            grader = subm['grader']

            # need to check for duplicate cell ids, see
            # https://github.com/jupyter/nbgrader/issues/1083

            # need to make sure the cell_type agrees with nbgrader cell_type
            # (students accidentally sometimes change it)

            # open the student's notebook
            try:
                f = open(subm['collected_assignment_path'], 'r')
                nb = json.load(f)
                f.close()
            except JSONDecodeError as e:
                msg = (f"JSON ERROR in student {student.name} {student.lms_id} assignment {assignment.name} "
                       f"grader {grader['name']} course name {course_name}" +
                       "This can happen if cleaning was previously abruptly stopped, leading to a corrupted file." +
                       "It might also happen if the student somehow deleted "
                       "their file and left a non-JSON file behind." +
                       "Either way, this workflow will fail now to prevent further damage; "
                       "please inspect the file and fix the issue" +
                       "(typically by manually re-copying the student work into the grader/submitted folder")

                sig = signals.FAIL(msg)
                sig.msg = msg
                raise sig
            # go through and
            # 1) make sure cell type agrees with nbgrader cell type
            # 2) delete the nbgrader metadata from any duplicated cells
            cell_ids = set()
            for cell in nb['cells']:
                # align celltype with nbgrader celltype
                try:
                    # ensure cell has both types by trying to read them
                    cell_type = cell['cell_type']
                    nbgrader_cell_type = cell['metadata']['nbgrader']['cell_type']
                    if cell_type != nbgrader_cell_type:
                        logger.info(
                            f"Student {student['name']} assignment {assignment['name']} grader {grader['name']} "
                            f"had incorrect cell type, {cell_type} != {nbgrader_cell_type}, cell ID = {cell_id}")
                        logger.info(f"Setting cell type to {nbgrader_cell_type} to avoid bugs in autograde")
                        # make cell_type align
                        cell['cell_type'] = nbgrader_cell_type
                except:
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
                except:
                    pass

                # delete nbgrader metadata from duplicated cells
                try:
                    cell_id = cell['metadata']['nbgrader']['grade_id']
                except:
                    continue
                if cell_id in cell_ids:
                    logger.info(
                        f"Student {student['name']} assignment {assignment['name']} grader {grader['name']} had a duplicate cell! ID = {cell_id}")
                    logger.info("Removing the nbgrader metainfo from that cell to avoid bugs in autograde")
                    cell['metadata'].pop('nbgrader', None)
                else:
                    cell_ids.add(cell_id)

            # write the sanitized notebook back to the submitted folder
            f = open(subm['collected_assignment_path'], 'w')
            json.dump(nb, f)
            f.close()

            subm['status'] = GradingStatus.PREPARED
    return subm_set


# ----------------------------------------------------------------------------------------------------------
@task
def autograde(config, subm_set):
    logger = get_run_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.PREPARED:
                if os.path.exists(subm['autograded_assignment_path']):
                    subm['status'] = GradingStatus.AUTOGRADED
                    continue

                logger.info(f"Autograding submission {subm['name']}")
                logger.info('Removing old autograding result from DB if it exists')
                try:
                    gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'], 'gradebook.db'))
                    gb.remove_submission(assignment['name'], config.grading_student_folder_prefix+subm['student']['id'])
                except MissingEntry as e:
                    pass
                finally:
                    gb.close()
                logger.info('Autograding...')
                res = run_container(config, 'nbgrader autograde --force '+
                                            '--assignment=' + assignment['name'] +
                                            ' --student='+config.grading_student_folder_prefix+subm['student']['id'],
                                    subm['grader']['folder'])

                # validate the results
                if 'ERROR' in res['log']:
                    logger.warning(f"Docker error autograding submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}")
                    logger.warning(f"May still continue if rudaux determines this error is nonfatal")
                #    msg = f"Docker error autograding submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}"
                #    sig = signals.FAIL(msg)
                #    sig.msg = msg
                #    raise sig
                # as long as we generate a file, assume success (avoids weird errors that dont actually cause a problem killing rudaux)
                if not os.path.exists(subm['autograded_assignment_path']):
                    msg = f"Docker error autograding submission {subm['name']}: did not generate expected file at {subm['autograded_assignment_path']}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                subm['status'] = GradingStatus.AUTOGRADED

    return subm_set

# ----------------------------------------------------------------------------------------------------------
@task
def check_manual_grading(config, subm_set):
    logger = get_run_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.AUTOGRADED:
                # check if the submission needs manual grading
                try:
                    gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'], 'gradebook.db'))
                    gb_subm = gb.find_submission(assignment['name'],
                                                 config.grading_student_folder_prefix+subm['student']['id'])
                    flag = gb_subm.needs_manual_grade
                except Exception as e:
                    msg = f"Error when checking whether submission {subm['name']} needs manual grading; error {str(e)}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                finally:
                    gb.close()

                # if the need manual grade flag is set, and we don't find the IGNORE_MANUAL_GRADING file
                # this is a hack to deal with the fact that sometimes nbgrader
                # just thinks an assignment needs manual grading
                # even when it doesn't, and there's nothing the TA can do to convince it otherwise.
                # when that happens, we just touch IGNORE_MANUAL_GRADING inside the folder
                if flag and not os.path.exists(os.path.join(subm['grader']['folder'], 'IGNORE_MANUAL_GRADING')):
                    subm['status'] = GradingStatus.NEEDS_MANUAL_GRADE
                else:
                    subm['status'] = GradingStatus.DONE_GRADING
    return subm_set


# ----------------------------------------------------------------------------------------------------------
@task
def generate_feedback(config, subm_set):
    logger = get_run_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.NOT_DUE or subm['status'] == GradingStatus.MISSING or os.path.exists(subm['generated_feedback_path']):
                continue
            logger.info(f"Generating feedback for submission {subm['name']}")

            attempts = 3
            for attempt in range(attempts):
                res = run_container(config, 'nbgrader generate_feedback --force '+
                                            '--assignment=' + assignment['name'] +
                                            ' --student=' + config.grading_student_folder_prefix+subm['student']['id'],
                                    subm['grader']['folder'])

                # validate the results
                #if 'ERROR' in res['log']:
                #    msg = f"Docker error generating feedback for submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}"
                #    sig = signals.FAIL(msg)
                #    raise sig
                # limit errors to just missing output
                if not os.path.exists(subm['generated_feedback_path']):
                    logger.info(f"Docker error generating feedback for submission {subm['name']}: did not generate expected file at {subm['generated_feedback_path']}")
                    if attempt < attempts-1:
                        logger.info("Trying again...")
                        continue
                    else:
                        msg = f"Docker error generating feedback for submission {subm['name']}: did not generate expected file at {subm['generated_feedback_path']}"
                        sig = signals.FAIL(msg)
                        raise sig

                # open the feedback form that was just generated and make sure the final grade lines up with the DB grade

                # STEP 1: load grades from feedback form (and check internal consistency with totals and individual grade cells)
                # the final grade and TOC on the form looks like
                # <div class="panel-heading">
                # <h4>tutorial_wrangling (Score: 35.0 / 44.0)</h4>
                # <div id="toc">
                # <ol>
                # <li><a href="#cell-b2ed899f3e35cfcb">Test cell</a> (Score: 1.0 / 1.0)</li>
                # ...
                # </ol>
                fdbk_html = None
                with open(subm['generated_feedback_path'], 'r') as f:
                    fdbk_html = f.read()
                fdbk_parsed = BeautifulSoup(fdbk_html, features="lxml")
                cell_tokens_bk = []
                cell_score_bk = []
                total_tokens = [s.strip(")(") for s in fdbk_parsed.body.find('div', {"id":"toc"}).find_previous_sibling('h4').text.split()]
                total = [float(total_tokens[i]) for i in [-3, -1]]
                running_totals = [0.0, 0.0]
                for item in fdbk_parsed.body.find('div', {"id":"toc"}).find('ol').findAll('li'):
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
                    logger.info(f"Docker error generating feedback for submission {subm['name']}: grade does not line up within feedback file!")
                    logger.info(f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  running_totals[1]: {running_totals[1]} total[1]: {total[1]}")
                    logger.info(f"Docker container log: \n {res['log']}")
                    logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n Cell Tokens: \n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                    logger.info(f"HTML for total:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find_previous_sibling('h4').text}")
                    logger.info(f"HTML for individual:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find('ol').findAll('li')}")
                    if attempt < attempts-1:
                        logger.info("Trying again...")
                        continue
                    else:
                        msg = f"Docker error generating feedback for submission {subm['name']}: grade does not line up within feedback file!"
                        sig = signals.FAIL(msg)
                        os.remove(subm['generated_feedback_path'])
                        raise(sig)

                # if assignment max doesn't equal sum of question maxes, warning; this can occur if student deleted test cell
                if abs(running_totals[1] - total[1]) > 1e-5:
                    logger.info(f"Docker warning generating feedback for submission {subm['name']}: total grade does not line up within feedback file (likely due to deleted grade cell)!")
                    logger.info(f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  running_totals[1]: {running_totals[1]} total[1]: {total[1]}")
                    logger.info(f"Docker container log: \n {res['log']}")
                    logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n Cell Tokens: \n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                    logger.info(f"HTML for total:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find_previous_sibling('h4').text}")
                    logger.info(f"HTML for individual:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find('ol').findAll('li')}")

                # STEP 2: load grades from gradebook and compare
                student = subm['student']
                try:
                    gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'] , 'gradebook.db'))
                    gb_subm = gb.find_submission(assignment['name'], config.grading_student_folder_prefix+student['id'])
                    score = gb_subm.score
                except Exception as e:
                    msg = f"Error when accessing the gradebook score for submission {subm['name']}; error {str(e)}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    os.remove(subm['generated_feedback_path'])
                    raise sig
                finally:
                    gb.close()

                # if feedback grade != canvas grade, error
                if abs(total[0] - score) > 1e-5:
                    logger.info(f"Docker error generating feedback for submission {subm['name']}: grade does not line up with DB!")
                    logger.info(f"running_totals[0]: {running_totals[0]} total[0]: {total[0]}  running_totals[1]: {running_totals[1]} total[1]: {total[1]} score: {score}")
                    logger.info(f"Docker container log: \n {res['log']}")
                    logger.info(f"Total tokens: \n {total_tokens} \n Total: \n {total} \n Cell Tokens: \n {cell_tokens_bk} \n Cell Scores: \n {cell_score_bk}")
                    logger.info(f"HTML for total:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find_previous_sibling('h4').text}")
                    logger.info(f"HTML for individual:\n {fdbk_parsed.body.find('div', {'id':'toc'}).find('ol').findAll('li')}")
                    logger.info(f"DB score: {score}")
                    if attempt < attempts-1:
                        logger.info("Trying again...")
                        continue
                    else:
                        msg = f"Docker error generating feedback for submission {subm['name']}: grade does not line up with DB!; docker container log: \n {res['log']}"
                        sig = signals.FAIL(msg)
                        os.remove(subm['generated_feedback_path'])
                        raise sig
                break

    return subm_set


# ----------------------------------------------------------------------------------------------------------
@task
def return_feedback(config, pastdue_frac, subm_set):
    logger = get_run_logger()
    # skip if pastdue frac not high enough or we haven't reached the earlist return date
    if pastdue_frac < config.return_solution_threshold:
        raise signals.SKIP(f"Assignment {subm_set['__name__']} has {pastdue_frac} submissions "+
                           f"past their due date, which is less than the return soln "+
                           f"threshold {config.return_solution_threshold} . Skipping feedback return.")
    if plm.now() < plm.parse(config.earliest_solution_return_date):
        raise signals.SKIP(f"We have not yet reached the earliest solution return date "+
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
            #else:
            #    logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
    return
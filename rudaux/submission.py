from enum import IntEnum
import os, shutil
import json
from json.decoder import JSONDecodeError
from nbgrader.api import Gradebook, MissingEntry
#from .course_api import GradeNotUploadedError
import pendulum as plm
from .course_api import put_grade
from .container import run_container
import prefect
from prefect import task
from prefect.engine import signals
from .snapshot import _get_snap_name
from .utilities import get_logger, recursive_chown
from bs4 import BeautifulSoup

class GradingStatus(IntEnum):
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    AUTOGRADED = 6
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10

def validate_config(config):
    # config.student_dataset_root
    # config.student_local_assignment_folder
    return config


# keep this function separate despite how simple it is
# in the future we may want to create 1 task per submission (right now it's 1 task per assignment to
# avoid network IO blowup with current Prefect 0.15.5)
# it would be great to do 1 task per submission so that we can individual signals.SKIP certain submissions.
# if eventually it is possible to do 1 task per submission, then this is where
# you would output a flattened list of every (student, assignment) pair
@task(checkpoint=False)
def initialize_submission_sets(config, course_infos, assignments, students, subm_infos):
    logger = get_logger()
    # verify that each list is of length (# courses)
    if len(course_infos) != len(assignments) or len(course_infos) != len(students):
        msg = (f"course_infos, assignments, and students lists must all have the same number "+
              f"of elements (number of courses in the group). ids: {len(course_infos)} assignments: {len(assignments)} students: {len(students)}")
        sig = signals.FAIL(msg)
        sig.msg = msg
        raise sig

    # if the lists are empty, just return empty submissions
    if len(course_infos) == 0:
        subms = []
        return subms

    # build the map from assignment name to indices
    asgn_map = {}
    for i in range(len(assignments)):
        a_list = assignments[i]
        for j in range(len(a_list)):
            if a_list[j]['name'] not in asgn_map:
                asgn_map[a_list[j]['name']] = len(assignments)*[None]
            asgn_map[a_list[j]['name']][i] = j

    # if None is still present in any of the lists, then there is
    # an assignment in one course not present in another; sig.FAIL
    if any([None in v for k, v in asgn_map.items()]):
        msg = f"one course has an assignment not present in another. Assignment index mapping: {asgn_map}"
        sig = signals.FAIL(msg)
        sig.msg = msg
        raise sig

    # construct the list of grouped assignments
    # data structure:
    # list of dicts, one for each assignment
    #     '__name__' : (assignment group name)
    #     'course_name' : {
    #              'assignment' : (assignment object)
    #              'submissions' : [  {
    #                                  'student' : (student object)
    #                                  'name'    : (submission name)
    #                                  'score'    : (score)
    #                                  'posted_at'    : (date score was posted on LMS)
    #                                  'late'    : (whether the subm is late)
    #                                  'missing'    : (whether the subm is missing)
    subm_sets = []
    for name in asgn_map:
        subm_set = {}
        subm_set['__name__'] = name
        for i in range(len(course_infos)):
            course_name = config.course_names[course_infos[i]['id']]
            course_info = course_infos[i]
            assignment = assignments[i][asgn_map[name][i]]
            subm_info = subm_infos[i]
            subm_set[course_name] = {}
            subm_set[course_name]['course_info'] = course_info
            subm_set[course_name]['assignment'] = assignment
            subm_set[course_name]['submissions'] = [{
                                        'student' : stu,
                                        'name' : f"{course_name}-{course_info['id']} : {assignment['name']}-{assignment['id']} : {stu['name']}-{stu['id']}"
                                        } for stu in students[i] if stu['status'] == 'active']
            for subm in subm_set[course_name]['submissions']:
                student = subm['student']
                subm['score'] = subm_info[assignment['id']][student['id']]['score']
                subm['posted_at'] = subm_info[assignment['id']][student['id']]['posted_at']
                subm['late'] = subm_info[assignment['id']][student['id']]['late']
                subm['missing'] = subm_info[assignment['id']][student['id']]['missing']
        subm_sets.append(subm_set)

    logger.info(f"Built a list of {len(subm_sets)} submission sets")
    return subm_sets

def _get_due_date(assignment, student):
    basic_date = assignment['due_at']

    #get overrides for the student
    overrides = [over for over in assignment['overrides'] if student['id'] in over['student_ids'] and (over['due_at'] is not None)]

    #if there was no override, return the basic date
    if len(overrides) == 0:
        return basic_date, None

    #if there was one, get the latest override date
    latest_override = overrides[0]
    for over in overrides:
        if over['due_at'] > latest_override['due_at']:
            latest_override = over

    #return the latest date between the basic and override dates
    if latest_override['due_at'] > basic_date:
        return latest_override['due_at'], latest_override
    else:
        return basic_date, None

def generate_build_subm_set_name(config, subm_set, **kwargs):
    return 'build-submset-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_build_subm_set_name)
def build_submission_set(config, subm_set):
    logger = get_logger()
    logger.info(f"Building submission set for assignment {subm_set['__name__']}")

    # check assignment date validity and build subm list
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']

        # check that assignment due/unlock dates exist
        if assignment['unlock_at'] is None or assignment['due_at'] is None:
            msg = f"Invalid unlock ({assignment['unlock_at']}) and/or due ({assignment['due_at']}) date for assignment {assignment['name']}"
            sig = signals.FAIL(msg)
            sig.msg = msg
            raise sig

        # if assignment dates are prior to course start, error
        if assignment['unlock_at'] < course_info['start_at'] or assignment['due_at'] < course_info['start_at']:
            msg = (f"Assignment {assignment['name']} unlock date ({assignment['unlock_at']}) "+
                  f"and/or due date ({assignment['due_at']}) is prior to the course start date "+
                  f"({course_info['start_at']}). This is often because of an old deadline from "+
                  f"a copied Canvas course from a previous semester. Please make sure assignment "+
                  f"deadlines are all updated to the current semester.")
            sig = signals.FAIL(msg)
            sig.msg = msg
            raise sig

        for subm in subm_set[course_name]['submissions']:
            student = subm['student']

            # check student registration date is valid
            if student['reg_date'] is None:
                msg = f"Invalid registration date for student {student['name']}, {student['id']} ({student['reg_date']})"
                sig = signals.FAIL(msg)
                sig.msg = msg
                raise sig

            # compute the submissions's due date, snap name, paths
            due_date, override = _get_due_date(assignment, student)
            subm['due_at'] = due_date
            subm['override'] = override
            subm['snap_name'] = _get_snap_name(course_name, assignment, override)
            subm['student_folder'] = os.path.join(config.student_dataset_root, student['id'])
            if override is None:
                subm['zfs_snap_path'] = config.student_dataset_root.strip('/') + '@' + subm['snap_name']
            else:
                subm['zfs_snap_path'] = subm['student_folder'].strip('/') + '@' + subm['snap_name']
            subm['snapped_assignment_path'] = os.path.join(subm['student_folder'],
                        '.zfs', 'snapshot', subm['snap_name'], config.student_local_assignment_folder,
                        assignment['name'], assignment['name']+'.ipynb')
            subm['soln_path'] = os.path.join(subm['student_folder'], assignment['name'] + '_solution.html')
            subm['fdbk_path'] = os.path.join(subm['student_folder'], assignment['name'] + '_feedback.html')

    # check whether all grades have been posted, and solutions/feedback returned (assignment is done). If so, skip
    all_posted = True
    all_returned = True
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        #check that all grades are posted
        all_posted = all_posted and all([subm['posted_at'] is not None for subm in subm_set[course_name]['submissions']])
        for subm in subm_set[course_name]['submissions']:
            # only check feedback/soln if student folder exists, i.e., they've logged into JHub
            if os.path.exists(subm['student_folder']):
                # check that soln was returned
                all_returned = all_returned and os.path.exists(subm['soln_path'])
                # check that fdbk was returned or assignment missing + score 0
                all_returned = all_returned and (os.path.exists(subm['fdbk_path']) or (subm['score'] == 0 and not os.path.exists(subm['snapped_assignment_path'])))
    if all_posted and all_returned:
        raise signals.SKIP(f"All grades are posted, all solutions returned, and all feedback returned for assignment {subm_set['__name__']}. Workflow done. Skipping.")

    logger.info(f"Done building submission set for assignment {subm_set['__name__']}")

    return subm_set


def generate_latereg_overrides_name(extension_days, subm_set, **kwargs):
    return 'lateregs-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_latereg_overrides_name)
def get_latereg_overrides(extension_days, subm_set, config):
    logger = get_logger()
    fmt = 'ddd YYYY-MM-DD HH:mm:ss'
    overrides = []
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']
        tz = course_info['time_zone']

        # skip the assignment if it isn't unlocked yet
        if assignment['unlock_at'] > plm.now():
            raise signals.SKIP(f"Assignment {assignment['name']} ({assignment['id']}) unlock date {assignment['unlock_at']} is in the future. Skipping.")

        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            regdate = student['reg_date']
            override = subm['override']

            to_remove = None
            to_create = None
            if regdate > assignment['unlock_at'] and assignment['unlock_at'] <= plm.from_format(config.registration_deadline, f'YYYY-MM-DD', tz=config.notify_timezone):
                #the late registration due date
                latereg_date = regdate.add(days=extension_days).in_timezone(tz).end_of('day').set(microsecond=0)
                if latereg_date > subm['due_at']:
                    logger.info(f"Student {student['name']} needs an extension on assignment {assignment['name']}")
                    logger.info(f"Student registration date: {regdate}    Status: {student['status']}")
                    logger.info(f"Assignment unlock: {assignment['unlock_at']}    Assignment deadline: {assignment['due_at']}")
                    logger.info("Current student-specific due date: " + subm['due_at'].in_timezone(tz).format(fmt) + " from override: " + str(True if (override is not None) else False))
                    logger.info('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
                    logger.info('Creating automatic late registration extension.')
                    if override is not None:
                        logger.info("Need to remove old override " + str(override['id']))
                        to_remove = override
                    to_create = {'student_ids' : [student['id']],
                                 'due_at' : latereg_date,
                                 'lock_at' : assignment['lock_at'],
                                 'unlock_at' : assignment['unlock_at'],
                                 'title' : student['name']+'-'+assignment['name']+'-latereg'}
                else:
                    continue
            else:
                continue
            overrides.append((assignment, to_create, to_remove))
    return overrides

def generate_assign_graders_name(subm_set, graders, **kwargs):
    return 'asgn-graders-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_assign_graders_name)
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
                collected_assignment_folder = os.path.join(grader['submissions_folder'], config.grading_student_folder_prefix+student['id'])
                if os.path.exists(collected_assignment_folder):
                    found = True
                    subm['grader'] = grader
                    break
            # if not assigned to anyone, choose the worker with the minimum current workload
            if not found:
                # sort graders in place and assign
                graders.sort(key = lambda g : g['workload'])
                min_grader = graders[0]
                min_grader['workload'] += 1
                subm['grader'] = min_grader

            # fill in the submission details that depend on a grader
            subm['collected_assignment_folder'] = os.path.join(subm['grader']['submissions_folder'], config.grading_student_folder_prefix+student['id'])
            subm['collected_assignment_path'] = os.path.join(subm['grader']['submissions_folder'],
                                                     config.grading_student_folder_prefix+student['id'],
                                                     assignment['name'], assignment['name'] + '.ipynb')
            subm['autograded_assignment_path'] = os.path.join(subm['grader']['autograded_folder'],
                                                     config.grading_student_folder_prefix+student['id'],
                                                     assignment['name'], assignment['name'] + '.ipynb')
            subm['generated_feedback_path'] = os.path.join(subm['grader']['feedback_folder'],
                                                     config.grading_student_folder_prefix+student['id'],
                                                     assignment['name'], assignment['name'] + '.html')
            subm['status'] = GradingStatus.ASSIGNED
    return subm_set


def generate_pastdue_frac_name(subm_set, **kwargs):
    return 'pastdue-frac-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_pastdue_frac_name)
def get_pastdue_fraction(subm_set):
    asgn_total = 0.
    asgn_outstanding = 0.
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        asgn_total += len(subm_set[course_name]['submissions'])
        asgn_outstanding += len([None for subm in subm_set[course_name]['submissions'] if subm['due_at'] > plm.now()])
    return (asgn_total - asgn_outstanding)/asgn_total

def generate_return_solns_name(config, pastdue_frac, subm_set, **kwargs):
    return 'retrn-solns-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_return_solns_name)
def return_solutions(config, pastdue_frac, subm_set):
    logger = get_logger()
    # skip if pastdue frac not high enough or we haven't reached the earlist return date
    if pastdue_frac < config.return_solution_threshold:
        raise signals.SKIP(f"Assignment {subm_set['__name__']} has {pastdue_frac} submissions "+
                           f"past their due date, which is less than the return soln "+
                           f"threshold {config.return_solution_threshold} . Skipping solution return.")
    if plm.now() < plm.parse(config.earliest_solution_return_date):
        raise signals.SKIP(f"We have not yet reached the earliest solution return date "+
                           f"{config.earliest_solution_return_date}. Skipping solution return.")

    for course_name in subm_set:
        if course_name == '__name__':
            continue
        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            #logger.info(f"Checking whether solution for submission {subm['name']} can be returned")
            if subm['due_at'] < plm.now():
                if not os.path.exists(subm['soln_path']):
                    logger.info(f"Returning solution submission {subm['name']}")
                    if os.path.exists(subm['student_folder']):
                        shutil.copy(subm['grader']['soln_path'], subm['soln_path'])
                        recursive_chown(subm['soln_path'], subm['grader']['unix_user'], subm['grader']['unix_group'])
                    else:
                        logger.warning(f"Warning: student folder {subm['student_folder']} doesnt exist. Skipping solution return.")
            #else:
            #    logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
    return

def generate_collect_subms_name(config, subm_set, **kwargs):
    return 'collct-subms-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_collect_subms_name)
def collect_submissions(config, subm_set):
    logger = get_logger()
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
                else:
                    logger.info(f"Submission {subm['name']} not yet collected. Collecting...")
                    os.makedirs(os.path.dirname(subm['collected_assignment_path']), exist_ok=True)
                    shutil.copy(subm['snapped_assignment_path'], subm['collected_assignment_path'])
                    recursive_chown(subm['collected_assignment_folder'], subm['grader']['unix_user'], subm['grader']['unix_group'])
                    subm['status'] = GradingStatus.COLLECTED
            else:
                subm['status'] = GradingStatus.COLLECTED
    return subm_set


def generate_clean_subms_name(subm_set, **kwargs):
    return 'clean-subms-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_clean_subms_name)
def clean_submissions(subm_set):
    logger = get_logger()

    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.COLLECTED:
                student = subm['student']
                grader = subm['grader']


                #need to check for duplicate cell ids, see
                #https://github.com/jupyter/nbgrader/issues/1083

                #need to make sure the cell_type agrees with nbgrader cell_type
                #(students accidentally sometimes change it)

                #open the student's notebook
                try:
                    f = open(subm['collected_assignment_path'], 'r')
                    nb = json.load(f)
                    f.close()
                except JSONDecodeError as e:
                    msg = (f"JSON ERROR in student {student['name']} {student['id']} assignment {assignment['name']} grader {grader['name']} course name {course_name}"+
                           "This can happen if cleaning was previously abruptly stopped, leading to a corrupted file."+
                           "It might also happen if the student somehow deleted their file and left a non-JSON file behind."+
                           "Either way, this workflow will fail now to prevent further damage; please inspect the file and fix the issue"+
                           "(typically by manually re-copying the student work into the grader/submitted folder")
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                #go through and
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
                        logger.info(f"Student {student['name']} assignment {assignment['name']} grader {grader['name']} had incorrect cell type, {cell_type} != {nbgrader_cell_type}, cell ID = {cell_id}")
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
                    logger.info(f"Student {student['name']} assignment {assignment['name']} grader {grader['name']} had a duplicate cell! ID = {cell_id}")
                    logger.info("Removing the nbgrader metainfo from that cell to avoid bugs in autograde")
                    cell['metadata'].pop('nbgrader', None)
                  else:
                    cell_ids.add(cell_id)

                #write the sanitized notebook back to the submitted folder
                f = open(subm['collected_assignment_path'], 'w')
                json.dump(nb, f)
                f.close()

                subm['status'] = GradingStatus.PREPARED
    return subm_set


def generate_autograde_name(subm_set, **kwargs):
    return 'autograde-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_autograde_name)
def autograde(config, subm_set):
    logger = get_logger()
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


def generate_checkmanual_name(subm_set, **kwargs):
    return 'check-manual-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_checkmanual_name)
def check_manual_grading(config, subm_set):
    logger = get_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.AUTOGRADED:
                # check if the submission needs manual grading
                try:
                    gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'], 'gradebook.db'))
                    gb_subm = gb.find_submission(assignment['name'], config.grading_student_folder_prefix+subm['student']['id'])
                    flag = gb_subm.needs_manual_grade
                except Exception as e:
                    msg = f"Error when checking whether submission {subm['name']} needs manual grading; error {str(e)}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                finally:
                    gb.close()

                # if the need manual grade flag is set, and we don't find the IGNORE_MANUAL_GRADING file
                # this is a hack to deal with the fact that sometimes nbgrader just thinks an assignment needs manual grading
                # even when it doesn't, and there's nothing the TA can do to convince it otherwise.
                # when that happens, we just touch IGNORE_MANUAL_GRADING inside the folder
                if flag and not os.path.exists(os.path.join(subm['grader']['folder'], 'IGNORE_MANUAL_GRADING')):
                    subm['status'] = GradingStatus.NEEDS_MANUAL_GRADE
                else:
                    subm['status'] = GradingStatus.DONE_GRADING
    return subm_set

def generate_collectgradingntfy_name(subm_set, **kwargs):
    return 'collect-grding-ntfy-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_collectgradingntfy_name)
def collect_grading_notifications(subm_set):
    logger = get_logger()
    notifications = {}
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.NEEDS_MANUAL_GRADE:
                guser = subm['grader']['user']
                gnm = subm['grader']['name']
                anm = assignment['name']
                if guser not in notifications:
                    notifications[guser] = {}
                if gnm not in notifications[guser]:
                    notifications[guser][gnm] = {'assignment' : anm, 'count' : 0}
                notifications[guser][gnm]['count'] += 1
    return notifications

def generate_collectpostingntfy_name(subm_set, **kwargs):
    return 'collect-psting-ntfy-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_collectpostingntfy_name)
def collect_posting_notifications(subm_set):
    logger = get_logger()
    notifications = []
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        for subm in subm_set[course_name]['submissions']:
            if subm['status'] == GradingStatus.DONE_GRADING and subm['posted_at'] == None:
                notifications.append( (course_name, assignment['name']) )
    return notifications

def generate_awaitcompletion_name(subm_set, **kwargs):
    return 'await-compl-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_awaitcompletion_name)
def await_completion(subm_set):
    all_done = True
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        all_done = all_done and all([subm['status'] != GradingStatus.NEEDS_MANUAL_GRADE for subm in subm_set[course_name]['submissions']])
    if not all_done:
        raise signals.SKIP(f"Submission set {subm_set['__name__']} not done grading yet. Skipping uploading grades / returning feedback")
    return subm_set

def generate_genfeedback_name(subm_set, **kwargs):
    return 'gen-fdbk-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_genfeedback_name)
def generate_feedback(config, subm_set):
    logger = get_logger()
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




def generate_retfeedback_name(subm_set, **kwargs):
    return 'retrn-fdbk-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_retfeedback_name)
def return_feedback(config, pastdue_frac, subm_set):
    logger = get_logger()
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
            #logger.info(f"Checking whether feedback for submission {subm['name']} can be returned")
            if subm['due_at'] < plm.now() and subm['status'] != GradingStatus.MISSING:
                if not os.path.exists(subm['generated_feedback_path']):
                    logger.warning(f"Warning: feedback file {subm['generated_feedback_path']} doesnt exist yet. Skipping feedback return.")
                    continue
                if not os.path.exists(subm['fdbk_path']):
                    logger.info(f"Returning feedback for submission {subm['name']}")
                    if os.path.exists(subm['student_folder']):
                        shutil.copy(subm['generated_feedback_path'], subm['fdbk_path'])
                        recursive_chown(subm['fdbk_path'], subm['grader']['unix_user'], subm['grader']['unix_group'])
                    else:
                        logger.warning(f"Warning: student folder {subm['student_folder']} doesnt exist. Skipping feedback return.")
            #else:
            #    logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
    return


def _compute_max_score(grader, assignment):
  #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
  #let's compute the max_score from the notebook manually then....
  release_nb_path = os.path.join(grader['folder'], 'release', assignment['name'], assignment['name']+'.ipynb')
  f = open(release_nb_path, 'r')
  parsed_json = json.load(f)
  f.close()
  pts = 0
  for cell in parsed_json['cells']:
    try:
      pts += cell['metadata']['nbgrader']['points']
    except Exception as e:
      #will throw exception if cells dont exist / not right type -- that's fine, it'll happen a lot.
      pass
  return pts

def generate_uploadgrade_name(subm_set, **kwargs):
    return 'upload-grds-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_uploadgrade_name)
def upload_grades(config, subm_set):
    logger = get_logger()
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']
        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            if subm['status'] == GradingStatus.DONE_GRADING and subm['score'] is None:
                logger.info(f"Uploading grade for submission {subm['name']}")
                logger.info(f"Obtaining score from the gradebook")
                try:
                    gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'] , 'gradebook.db'))
                    gb_subm = gb.find_submission(assignment['name'], config.grading_student_folder_prefix+student['id'])
                    score = gb_subm.score
                except Exception as e:
                    msg = f"Error when accessing the gradebook score for submission {subm['name']}; error {str(e)}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                finally:
                    gb.close()
                logger.info(f"Score: {score}")

                logger.info(f"Computing the max score from the release notebook")
                try:
                    max_score = _compute_max_score(subm['grader'], assignment)
                except Exception as e:
                    msg = f"Error when trying to compute the max score for submission {subm['name']}; error {str(e)}"
                    sig = signals.FAIL(msg)
                    sig.msg = msg
                    raise sig
                logger.info(f"Max Score: {max_score}")

                pct = "{:.2f}".format(100*score/max_score)
                logger.info(f"Percent grade: {pct}")

                logger.info(f"Uploading to Canvas...")
                subm['score'] = pct
                put_grade(config, course_info['id'], student, assignment, subm['score'])
    return subm_set



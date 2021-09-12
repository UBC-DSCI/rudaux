from enum import IntEnum
import os, shutil, pwd
import json
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
        sig = signals.FAIL(f"course_infos, assignments, and students lists must all have the same number "+
                           f"of elements (number of courses in the group). ids: {len(course_infos)} assignments: {len(assignments)} students: {len(students)}")
        sig.course_infos = course_infos
        sig.assignments = assignments
        sig.students = students
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
        sig = signals.FAIL(f"one course has an assignment not present in another. Assignment index mapping: {asgn_map}")
        sig.course_infos = course_infos
        sig.assignments = assignments
        sig.students = students
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
    # check assignment date validity and build subm list
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']

        # check that assignment due/unlock dates exist
        if assignment['unlock_at'] is None or assignment['due_at'] is None:
            sig = signals.FAIL(f"Invalid unlock ({assignment['unlock_at']}) and/or due ({assignment['due_at']}) date for assignment {assignment['name']}")
            sig.assignment = assignment
            raise sig

        # if assignment dates are prior to course start, error
        if assignment['unlock_at'] < course_info['start_at'] or assignment['due_at'] < course_info['start_at']:
            sig = signals.FAIL(f"Assignment {assignment['name']} unlock date ({assignment['unlock_at']}) "+
                               f"and/or due date ({assignment['due_at']}) is prior to the course start date "+
                               f"({course_info['start_at']}). This is often because of an old deadline from "+
                               f"a copied Canvas course from a previous semester. Please make sure assignment "+
                               f"deadlines are all updated to the current semester.")
            sig.assignment = assignment
            raise sig

        for subm in subm_set[course_name]['submissions']:
            student = subm['student']

            # check student registration date is valid
            if student['reg_date'] is None:
                sig = signals.FAIL(f"Invalid registration date for student {student['name']}, {student['id']} ({student['reg_date']})")
                sig.student = student
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

    return subm_set


def generate_latereg_overrides_name(extension_days, subm_set, **kwargs):
    return 'lateregs-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_latereg_overrides_name)
def get_latereg_overrides(extension_days, subm_set):
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
            if regdate > assignment['unlock_at']:
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
                    #logger.info("Current extension meets or exceeds the late registration extension.")
                    continue
                    #raise signals.SKIP("Current due date for student {student['name']}, assignment {assignment['name']} after late registration date; no override modifications required.")
            else:
                continue
                #raise signals.SKIP("Assignment {assignment['name']} unlocks after student {student['name']} registration date; no extension required.")
            overrides.append((assignment, to_create, to_remove))
            #return (assignment, to_create, to_remove)
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
            subm['collected_assignment_folder'] = os.path.join(grader['submissions_folder'], config.grading_student_folder_prefix+student['id'])
            subm['collected_assignment_path'] = os.path.join(subm['grader']['submissions_folder'],
                                                     config.grading_student_folder_prefix+student['id'],
                                                     assignment['name'], assignment['name'] + '.ipynb')
            subm['autograded_assignment_path'] = os.path.join(subm['grader']['autograded_folder'],
                                                     config.grading_student_folder_prefix+student['id'],
                                                     assignment['name'], assignment['name'] + '.ipynb')
            subm['feedback_path'] = os.path.join(subm['grader']['feedback_folder'],
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
                        try:
                            shutil.copy(subm['grader']['soln_path'], subm['soln_path'])
                            os.chown(subm['soln_path'], subm['grader']['unix_uid'], subm['grader']['unix_uid'])
                        except Exception as e:
                            raise signals.FAIL(str(e))
                    else:
                        logger.warning(f"Warning: student folder {subm['student_folder']} doesnt exist. Skipping solution return.")
            else:
                logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
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
                    if subm['score'] is None:
                        logger.info(f"Submission {subm['name']} is missing. Uploading score of 0.")
                        subm['status'] = GradingStatus.MISSING
                        subm['score'] = 0.
                        put_grade(config, course_info['id'], student, assignment, subm['score'])
                else:
                    logger.info(f"Submission {subm['name']} not yet collected. Collecting...")
                    try:
                        os.makedirs(os.path.dirname(subm['collected_assignment_path']), exist_ok=True)
                        shutil.copy(subm['snapped_assignment_path'], subm['collected_assignment_path'])
                        recursive_chown(subm['collected_assignment_folder'], subm['grader']['unix_uid'])
                        subm['status'] = GradingStatus.COLLECTED
                    except Exception as e:
                        raise signals.FAIL(str(e))
                    #logger.info("Submission collected.")
            else:
                #logger.info("Submission already collected.")
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
                #open the student's notebook
                try:
                    f = open(subm['collected_assignment_path'], 'r')
                    nb = json.load(f)
                    f.close()
                except Exception as e:
                    raise signals.FAIL(str(e))
                #go through and delete the nbgrader metadata from any duplicated cells
                cell_ids = set()
                for cell in nb['cells']:
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
                try:
                    f = open(subm['collected_assignment_path'], 'w')
                    json.dump(nb, f)
                    f.close()
                except Exception as e:
                    raise signals.FAIL(str(e))

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
                logger.info(f"Autograding submission {subm['name']}")

                if os.path.exists(subm['autograded_assignment_path']):
                    logger.info('Assignment previously autograded & validated.')
                    subm['status'] = GradingStatus.AUTOGRADED
                    continue

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
                    raise signals.FAIL(f"Docker error autograding submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}")
                if not os.path.exists(subm['autograded_assignment_path']):
                    raise signals.FAIL(f"Docker error autograding submission {subm['name']}: did not generate expected file at {subm['autograded_assignment_path']}")
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
                    sig = signals.FAIL(f"Error when checking whether submission {subm['name']} needs manual grading; error {str(e)}")
                    sig.e = e
                    sig.subm = subm
                    raise sig
                finally:
                    gb.close()

                if flag:
                    subm['status'] = GradingStatus.NEEDS_MANUAL_GRADE
                else:
                    subm['status'] = GradingStatus.DONE_GRADING
    return subm_set

@task(checkpoint=False)
def collect_grading_notifications(subm_sets):
    for subm_set in subm_sets:
        #TODO
        pass
    return 0

@task(checkpoint=False)
def collect_posting_notifications(notifications, subm_sets):
    for subm_set in subm_sets:
        #TODO
        pass
    return 0

def generate_awaitcompletion_name(subm_set, **kwargs):
    return 'await-compl-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_awaitcompletion_name)
def await_completion(subm_set):
    all_done = True
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        all_done = all_done and all([subm['status'] in [GradingStatus.MISSING, GradingStatus.DONE_GRADING] for subm in subm_set[course_name]['submissions']])
    if not all_done:
        raise signals.SKIP("Submission set {subm_set['__name__']} not done grading yet. Skipping uploading grades / returning feedback")
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
            if os.path.exists(subm['feedback_path']):
                logger.info('Feedback generated previously.')
                continue
            res = run_container(config, 'nbgrader generate_feedback --force '+
                                        '--assignment=' + assignment['name'] +
                                        ' --student=' + config.grading_student_folder_prefix+subm['student']['id'],
                                subm['grader']['folder'])

            # validate the results
            if 'ERROR' in res['log']:
                raise signals.FAIL(f"Docker error generating feedback for submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}")
            if not os.path.exists(subm['feedback_path']):
                raise signals.FAIL(f"Docker error generating feedback for submission {subm['name']}: did not generate expected file at {subm['feedback_path']}")
    return subm_set


def generate_retfeedback_name(subm_set, **kwargs):
    return 'retrn-fdbk-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_retfeedback_name)
def return_feedback(config, pastdue_frac, subm):
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
            if subm['due_at'] < plm.now():
                if not os.path.exists(fdbk_path_student):
                    logger.info(f"Returning feedback for submission {subm['name']}")
                    if os.path.exists(fdbk_folder_student):
                        try:
                            shutil.copy(fdbk_path_grader, fdbk_path_student)
                            os.chown(fdbk_path_student, subm['grader']['unix_uid'], subm['grader']['unix_uid'])
                        except Exception as e:
                            raise signals.FAIL(str(e))
                    else:
                        logger.warning(f"Warning: student folder {subm['student_folder']} doesnt exist. Skipping solution return.")
            else:
                logger.info(f"Not returnable yet; the student-specific due date ({subm['due_at']}) has not passed.")
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
            logger.info(f"Uploading grade for submission {subm['name']}")
            if subm['score'] is not None:
                logger.info(f"Grade already uploaded.")
                continue

            logger.info(f"Obtaining score from the gradebook")
            try:
                gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'] , 'gradebook.db'))
                gb_subm = gb.find_submission(assignment['name'], config.grading_student_folder_prefix+student['id'])
                score = gb_subm.score
            except Exception as e:
                sig = signals.FAIL(f"Error when accessing the gradebook score for submission {subm['name']}; error {str(e)}")
                sig.e = e
                sig.subm = subm
                raise sig
            finally:
                gb.close()
            logger.info(f"Score: {score}")

            logger.info(f"Computing the max score from the release notebook")
            try:
                max_score = _compute_max_score(subm['grader'], assignment)
            except Exception as e:
                sig = signals.FAIL(f"Error when trying to compute the max score for submission {subm['name']}; error {str(e)}")
                sig.e = e
                sig.subm = subm
                raise sig
            logger.info(f"Max Score: {max_score}")

            self.score = score
            self.max_score = max_score
            pct = "{:.2f}".format(100*score/max_score)
            logger.info(f"Percent grade: {pct}")

            logger.info(f"Uploading to Canvas...")
            subm['score'] = pct
            put_grade(config, course_info['id'], student, assignment, subm['score'])
    return subm_set



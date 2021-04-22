from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool
from enum import IntEnum
import os, shutil, pwd
import json
from nbgrader.api import Gradebook, MissingEntry
from .docker import DockerError
from .canvas import GradeNotUploadedError
import pendulum as plm
from .course_api import put_grade
from .container import run_container

class GradingStatus(IntEnum):
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    AUTOGRADED = 6
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10

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

def _get_snap_name(config, assignment, override):
    return config.course_name+'-'+assignment['name']+'-' + assignment['id'] + ('' if override is None else override['id'])

@task
def validate_config(config):
    # config.student_dataset_root
    # config.student_local_assignment_folder
    return config


# used to construct the product of all student x assignments and assign to graders
@task
def build_submissions(assignments, students, subm_info, graders):
    logger = prefect.context.get("logger")
    logger.info(f"Initializing submission objects")
    subms = []
    for asgn in assignments:
        for stu in students:
            subm = {}
            # initialize values that are *not* potential failure points here
            subm['assignment'] = asgn
            subm['student'] = stu

            # search for this student in the grader folders 
            found = False
            for grader in graders:
                collected_assignment_path = os.path.join(grader['submissions_folder'], 
                                                         config.grading_student_folder_prefix+stu['id'], 
                                                         asgn['name'] + '.ipynb')
                if os.path.exists(collected_assignment_path):
                    found = True
                    subm['grader'] = grader
                    break
            # if not assigned to anyone, choose the worker with the minimum current workload
            if not found:
                # TODO I believe sorted makes a copy, so I need to find the original grader in the list to increase their workload
                # should debug this to make sure workloads are actually increasing, and also figure out whether it's possible to simplify
                min_grader = sorted(graders, key = lambda g : g['workload'])[0]
                graders[graders.index(min_grader)]['workload'] += 1
                subm['grader'] = graders[graders.index(min_grader)]

            subm['name'] = f"({asgn['name']}-{asgn['id']},{stu['name']}-{stu['id']},{subm['grader']['name']})"  
            
            subms.append(subm)
    return subms

# validate each submission, skip if not due yet 
@task
def initialize_submission(config, course_info, subm):
    logger = prefect.context.get("logger")
    logger.info(f"Validating submission {submission['name']}")
    assignment = subm['assignment']
    student = subm['student']

    # check student regdate, assignment due/unlock dates exist
    if assignment['unlock_at'] is None or assignment['due_at'] is None:
         sig = signals.FAIL(f"Invalid unlock ({assignment['unlock_at']}) and/or due ({assignment['due_at']}) date for assignment {assignment['name']}")
         sig.assignment = assignment
         raise sig
    if assignment['unlock_at'] < course_info['start_at'] or assignment['due_at'] < course_info['start_at']:
         sig = signals.FAIL(f"Assignment {assignment['name']} unlock date ({assignment['unlock_at']}) and/or due date ({assignment['due_at']}) is prior to the course start date ({course_info['start_at']}). This is often because of an old deadline from a copied Canvas course from a previous semester. Please make sure assignment deadlines are all updated to the current semester.")
         sig.assignment = assignment
         raise sig
    if student['reg_date'] is None:
         sig = signals.FAIL(f"Invalid registration date for student {student['name']}, {student['id']} ({student['reg_date']})")
         sig.student = student
         raise sig

    # if student is inactive, skip
    if student['status'] != 'active':
         raise signals.SKIP(f"Student {student['name']} is inactive. Skipping their submissions.")

    # initialize values that are potential failure points here
    due_date, override = _get_due_date(assignment, student)
    subm['due_at'] = due_date
    subm['override'] = override
    subm['snap_name'] = _get_snap_name(config, assignment, override) 
    if override is None:
        subm['zfs_snap_path'] = config.student_dataset_root.strip('/') + '@' + subm['snap_name']
    else:
        subm['zfs_snap_path'] = os.path.join(config.student_dataset_root, student['id']).strip('/') + '@' + subm['snap_name']
    subm['attached_folder'] = os.path.join(config.grading_attached_student_dataset_root, student['id'])
    subm['snapped_assignment_path'] = os.path.join(subm['attached_folder'], 
                '.zfs', 'snapshot', subm['snap_name'], config.student_local_assignment_folder, 
                assignment['name'], assignment['name']+'.ipynb')
    subm['soln_path'] = os.path.join(subm['attached_folder'], assignment['name'] + '_solution.html')
    subm['fdbk_path'] = os.path.join(subm['attached_folder'], assignment['name'] + '_feedback.html')
    subm['score'] = subm_info[assignment['id']][student['id']]['score']
    subm['posted_at'] = subm_info[assignment['id']][student['id']]['posted_at']
    subm['late'] = subm_info[assignment['id']][student['id']]['late']
    subm['missing'] = subm_info[assignment['id']][student['id']]['missing']
    subm['collected_assignment_path'] = os.path.join(subm['grader']['submissions_folder'], 
                                                     config.grading_student_folder_prefix+subm['student']['id'], 
                                                     subm['assignment']['name'], subm['assignment']['name'] + '.ipynb')
    subm['autograded_assignment_path'] = os.path.join(subm['grader']['autograded_folder'], 
                                                     config.grading_student_folder_prefix+subm['student']['id'], 
                                                     subm['assignment']['name'], subm['assignment']['name'] + '.ipynb')
    subm['feedback_path'] = os.path.join(subm['grader']['feedback_folder'], 
                                                     config.grading_student_folder_prefix+subm['student']['id'], 
                                                     subm['assignment']['name'], subm['assignment']['name'] + '.html')
    subm['status'] = GradingStatus.ASSIGNED

    return subm

@task
def get_pastdue_fractions(config, course_info, submissions):
    assignment_totals = {}
    assignment_outstanding = {}
    assignment_fracs = {}
    for subm in submissions:
        assignment = subm['assignment'] 
        anm = assignment['name']
        if anm not in assignment_totals:
            assignment_totals[anm] = 0
        if anm not in assignment_outstanding:
            assignment_outstanding[anm] = 0
        
        assignment_totals[anm] += 1
        if subm['due_at'] > plm.now():
            assignment_outstanding[anm] += 1

    for k, v in assignment_totals.items():
        assignment_fracs[k] = (v - assignment_outstanding[k])/v

    return assignment_fracs

@task
def return_solution(config, course_info, assignment_fracs, subm):
    logger = prefect.context.get("logger")
    assignment = subm['assignment'] 
    anm = assignment['name']
    logger.info(f"Checking whether solution for submission {subm['name']} can be returned")
    if subm['due_at'] > plm.now() and assignment_fracs[anm] > config.return_solution_threshold and plm.now() > plm.parse(config.earliest_solution_return_date, tz=course_info['time_zone']):
        logger.info(f"Returning solution submission {subm['name']}")
        if not os.path.exists(subm['soln_path']):
            if os.path.exists(subm['attached_folder']):
                try:
                    shutil.copy(subm['grader']['soln_path'], subm['soln_path']) 
                    os.chown(subm['soln_path'], subm['grader']['unix_uid'], subm['grader']['unix_uid'])
                except Exception as e:
                    raise signals.FAIL(str(e))
            else:
                logger.warning(f"Warning: student folder {subm['attached_folder']} doesnt exist. Skipping solution return.")
    else:
        logger.info(f"Not returnable yet. Either the student-specific due date ({subm['due_at']}) has not passed, threshold not yet reached ({assignment_fracs[anm]} <= {config.return_solution_threshold}) or not yet reached the earliest possible solution return date")

    return submission

@task
def collect_submission(config, subm):
    logger = prefect.context.get("logger")
    logger.info(f"Collecting submission {subm['name']}...")
    # if the submission is due in the future, skip
    if subm['due_at'] > plm.now():
         subm['status'] = GradingStatus.NOT_DUE
         raise signals.SKIP(f"Submission {subm['name']} is due in the future. Skipping.")

    if not os.path.exists(subm['collected_assignment_path']):
        if not os.path.exists(subm['snapped_assignment_path']):
            logger.info(f"Submission {subm['name']} is missing. Uploading score of 0.")
            subm['status'] = GradingStatus.MISSING
            subm['score'] = 0.
            put_grade(config, subm)
            raise signals.SKIP(f"Skipping the remainder of the task flow for submission {subm['name']}.")
        else:
            shutil.copy(subm['snapped_assignment_path'], subm['collected_assignment_path'])
            os.chown(subm['collected_assignment_path'], subm['grader']['unix_uid'], subm['grader']['unix_uid'])
            subm['status'] = GradingStatus.COLLECTED
            logger.info("Submission collected.")
    else:
        logger.info("Submission already collected.")
        subm['status'] = GradingStatus.COLLECTED
    return subm

@task
def clean_submission(config, subm):
    logger = prefect.context.get("logger")

    #need to check for duplicate cell ids, see
    #https://github.com/jupyter/nbgrader/issues/1083
    #open the student's notebook
    f = open(subm['collected_assignment_path'], 'r')
    nb = json.load(f)
    f.close()
    
    #go through and delete the nbgrader metadata from any duplicated cells
    cell_ids = set()
    for cell in nb['cells']:
      try:
        cell_id = cell['metadata']['nbgrader']['grade_id']
      except:
        continue
      if cell_id in cell_ids:
        logger.info(f"Student {student['name']} assignment {assignment['name']} grader {grader} had a duplicate cell! ID = {cell_id}")
        logger.info("Removing the nbgrader metainfo from that cell to avoid bugs in autograde")
        cell['metadata'].pop('nbgrader', None)
      else:
        cell_ids.add(cell_id)
    
    #write the sanitized notebook back to the submitted folder
    f = open(subm['collected_assignment_path'], 'w')
    json.dump(nb, f)
    f.close()

    subm['status'] = GradingStatus.PREPARED

    return subm

@task
def autograde(config, subm):
    logger = prefect.context.get("logger")
    logger.info(f"Autograding submission {subm['name']}")

    if os.path.exists(subm['autograded_assignment_path']):
        logger.info('Assignment previously autograded & validated.')
        subm['status'] = GradingStatus.AUTOGRADED
        return subm

    logger.info('Removing old autograding result from DB if it exists')
    try:
        gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'], 'gradebook.db'))
        gb.remove_submission(subm['assignment']['name'], config.grading_student_folder_prefix+subm['student']['id'])
    except MissingEntry as e:
        pass
    finally:
        gb.close()
    logger.info('Autograding...')
    res = run_container(config, 'nbgrader autograde --force --assignment=' + subm['assignment']['name'] + ' --student='+config.grading_student_folder_prefix+subm['student']['id'], subm['grader']['folder'])

    # validate the results
    if 'ERROR' in res['log']:
        raise signals.FAIL(f"Docker error autograding submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}")
    if not os.path.exists(subm['autograded_assignment_path']):
        raise signals.FAIL(f"Docker error autograding submission {subm['name']}: did not generate expected file at {subm['autograded_assignment_path']}")

    return subm

@task
def wait_for_manual_grading(config, subm): 
    logger = prefect.context.get("logger")
    logger.info(f"Checking whether submission {subm['name']} needs manual grading")
        
    # check if the submission needs manual grading
    try:
        gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'], 'gradebook.db'))
        gb_subm = gb.find_submission(subm['assignment']['name'], config.grading_student_folder_prefix+subm['student']['id'])
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
        raise signals.SKIP(f"Submission {subm['name']} still waiting for manual grading. Skipping the remainder of this task.")
        
    logger.info("Done grading for submission {subm['name']}.")
    subm['status'] = GradingStatus.DONE_GRADING
    return subm

@task(skip_on_upstream_skip = False)
def get_complete_assignments(config, assignments, submissions):
    complete_tokens = []
    for asgn in assignments:
        if all([ (subm['status'] == GradingStatus.DONE_GRADING or subm['status'] == GradingStatus.MISSING) for subm in submissions if subm['assignment']['id'] == asgn['id']]):
            complete_tokens.append(asgn['id'])
    return complete_tokens

@task
def wait_for_completion(config, complete_ids, subm):
    if subm['assignment']['id'] in complete_ids:
        raise signals.SKIP("Submission {subm['name']} : other submissions for this assignment not done grading yet. Skipping remainder of this workflow (uploading grades / returning feedback)")
    return subm

@task
def generate_feedback(config, subm):
    logger = prefect.context.get("logger")
    logger.info(f"Generating feedback for submission {subm['name']}")

    if os.path.exists(subm['feedback_path']):
        logger.info('Feedback generated previously.')
        subm['status'] = GradingStatus.FEEDBACK_GENERATED
        return subm
    res = run_container(config, 'nbgrader generate_feedback --force --assignment=' + subm['assignment']['name'] + ' --student=' + config.grading_student_folder_prefix+subm['student']['id'], subm['grader']['folder'])

    # validate the results
    if 'ERROR' in res['log']:
        raise signals.FAIL(f"Docker error generating feedback for submission {subm['name']}: exited with status {res['exit_status']},  {res['log']}")
    if not os.path.exists(subm['feedback_path']):
        raise signals.FAIL(f"Docker error generating feedback for submission {subm['name']}: did not generate expected file at {subm['feedback_path']}")

    subm['status'] = GradingStatus.FEEDBACK_GENERATED
    return subm


# TODO this func still needs some work
@task
def return_feedback(config, course_info, assignment_fracs, subm):
    logger = prefect.context.get("logger")
    assignment = subm['assignment'] 
    anm = assignment['name']
    logger.info(f"Checking whether feedback for submission {subm['name']} can be returned")
    if subm['due_at'] > plm.now() and assignment_fracs[anm] > config.return_solution_threshold and plm.now() > plm.parse(config.earliest_solution_return_date, tz=course_info['time_zone']):
        logger.info(f"Returning feedback for submission {subm['name']}")
        if not os.path.exists(fdbk_path_student):
            if os.path.exists(fdbk_folder_student):
                try:
                    shutil.copy(fdbk_path_grader, fdbk_path_student) 
                    os.chown(fdbk_path_student, subm['grader']['unix_uid'], subm['grader']['unix_uid'])
                except Exception as e:
                    print('Error occured when returning feedback.')
                    print(e)
                    self.error = e
                    return SubmissionStatus.ERROR
            else:
                print('Warning: student folder ' + str(fdbk_folder_student) + ' doesnt exist. Skipping feedback return.')
    else:
        logger.info(f"Feedback not returnable yet. Either the threshold has not yet been reached ({assignment_fracs[anm]} <= {config.return_solution_threshold}) or not yet reached the earliest possible solution return date")
    return subm


def _compute_max_score(config, subm):
  #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
  #let's compute the max_score from the notebook manually then....
  release_nb_path = os.path.join(subm['grader']['folder'], 'release', subm['assignment']['name'], subm['assignment']['name']+'.ipynb')
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

@task
def upload_grade(config, subm):
    logger = prefect.context.get("logger")
    logger.info(f"Uploading grade for submission {subm['name']}")
    if subm['score'] is not None:
        raise signals.SKIP("Grade already uploaded.")

    logger.info(f"Obtaining score from the gradebook")
    try:
        gb = Gradebook('sqlite:///'+os.path.join(subm['grader']['folder'] , 'gradebook.db'))
        gb_subm = gb.find_submission(subm['assignment']['name'], config.grading_student_folder_prefix+subm['student']['id'])
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
        max_score = _compute_max_score(config, subm)
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
    put_grade(config, subm)
    
    return subm

@task
def get_latereg_override(config, submission):
    logger = prefect.context.get("logger")
    tz = course_info['time_zone']
    fmt = 'ddd YYYY-MM-DD HH:mm:ss'
    
    assignment = submission['assignment']
    student = submission['student']

    logger.info(f"Checking if student {student['name']} needs an extension on assignment {assignment['name']}")
    regdate = student['reg_date']
    logger.info(f"Student registration date: {regdate}    Status: {student['status']}")
    logger.info(f"Assignment unlock: {assignment['unlock_at']}    Assignment deadline: {assignment['due_at']}")
    to_remove = None
    to_create = None
    if regdate > assignment['unlock_at']:
        logger.info("Assignment unlock date after student registration date. Extension required.")
        #the late registration due date
        latereg_date = regdate.add(days=config.latereg_extension_days)
        logger.info("Current student-specific due date: " + submission['due_at'].in_timezone(tz).format(fmt) + " from override: " + str(True if (submission['override'] is not None) else False))
        logger.info('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
        if latereg_date > submission['due_at']:
            logger.info('Creating automatic late registration extension to ' + latereg_date.in_timezone(tz).format(fmt)) 
            if override is not None:
                logger.info("Need to remove old override " + str(override['id']))
                to_remove = override
            to_create = {'student_ids' : [student['id']],
                         'due_at' : latereg_date,
                         'lock_at' : assignment['lock_at'],
                         'unlock_at' : assignment['unlock_at'],
                         'title' : student['name']+'-'+assignment['name']+'-latereg'}
        else:
            raise signals.SKIP("Current due date for student {student['name']}, assignment {assignment['name']} after late registration date; no override modifications required.")
    else:
        raise signals.SKIP("Assignment {assignment['name']} unlocks after student {student['name']} registration date; no extension required.")

    return (assignment, to_create, to_remove)

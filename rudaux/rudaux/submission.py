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

class GradingStatus(IntEnum):
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    NEEDS_AUTOGRADE = 5
    AUTOGRADED = 6
    AUTOGRADE_FAILED_PREVIOUSLY = 7
    AUTOGRADE_FAILED = 8
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10
    GRADE_UPLOADED = 11
    NEEDS_FEEDBACK = 12
    FEEDBACK_GENERATED = 13
    FEEDBACK_FAILED_PREVIOUSLY = 14
    FEEDBACK_FAILED = 15
    NEEDS_POST = 16
    DONE = 17



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
            subm['name'] = f"({asgn['name']}-{asgn['id']},{stu['name']}-{stu['id']})"  

            # search for this student in the grader folders 
            found = False
            for grader in graders:
                collected_assignment_path = os.path.join(grader['submissions_folder'], 
                                                         config.grading_collected_student_folder_prefix+stu['id'], 
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
    subm['collected_assignment_path'] = os.path.join(grader['submissions_folder'], asgn_subms[i]['student']['id'], asgn_subms[i]['assignment']['name'] + '.ipynb')
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
            try:
                put_grade(config, subm)
            except Exception as e: 
                sig = signals.FAIL(f"Error when uploading missing assignment grade of 0 for submission {subm['name']}")
                sig.subm = subm
                sig.e = e
                raise sig 
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

    return subm

# TODO 
@task
def autograde(config, subm):
    logger = prefect.context.get("logger")

    #run_container(config, command, homedir = None)
 
    #self.autograde_docker_job_id = docker.submit('nbgrader autograde --force --assignment=' + self.asgn.name + ' --student='+self.student_prefix+self.stu.canvas_id, self.grader_repo_path)


    # create the autograded assignment file path
    self.autograded_assignment_path = os.path.join(self.grader_repo_path, self.grader_local_autograded_folder)
    self.autograde_fail_flag_path = os.path.join(self.grader_repo_path, 'autograde_failed_'+self.asgn.name+'-'+self.stu.canvas_id)

    print('Autograding submission ' + self.asgn.name+':'+self.stu.canvas_id)

    if os.path.exists(self.autograde_fail_flag_path):
        print('Autograde failed previously. Returning')
        return SubmissionStatus.AUTOGRADE_FAILED_PREVIOUSLY

    if os.path.exists(self.autograded_assignment_path):
        print('Assignment previously autograded & validated.')
        return SubmissionStatus.AUTOGRADED
    else:
        print('Removing old autograding result from DB if it exists')
        try:
            gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
            gb.remove_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
        except MissingEntry as e:
            pass
        finally:
            gb.close()
        print('Submitting job to docker pool for autograding')
        self.autograde_docker_job_id = docker.submit('nbgrader autograde --force --assignment=' + self.asgn.name + ' --student='+self.student_prefix+self.stu.canvas_id, self.grader_repo_path)
        return SubmissionStatus.NEEDS_AUTOGRADE

def check_grading(self, canvas, docker_results):
    if self.autograde_docker_job_id is not None:
        print('Checking autograding for submission ' + self.asgn.name+':'+self.stu.canvas_id)
        try:
            self.validate_docker_result(self.autograde_docker_job_id, docker_results, self.autograded_assignment_path)
        except DockerError as e:
            print('Autograder failed.')
            print(e.message)
            print(e.docker_output)
            self.error = e
            #create the fail flag file
            with open(self.autograde_fail_flag_path, 'wb') as f:
                pass
            jupyter_uid = pwd.getpwnam('jupyter').pw_uid
            os.chown(self.autograde_fail_flag_path, jupyter_uid, jupyter_uid)
            return SubmissionStatus.AUTOGRADE_FAILED
        print('Valid autograder result.')
        self.autograde_docker_job_id = None
        
    # check if the submission needs manual grading
    print('Checking whether submission ' + self.asgn.name+':'+self.stu.canvas_id + ' needs manual grading')
    try:
        if self.needs_manual_grading():
            print('Still needs manual grading.') 
            return SubmissionStatus.NEEDS_MANUAL_GRADE
    except Exception as e:
        print('Error when checking whether subm needs manual grading')
        print(e)
        self.error =e
        return SubmissionStatus.ERROR
        
    print('Done grading for ' + self.asgn.name+':'+self.stu.canvas_id )
    return SubmissionStatus.DONE_GRADING

def needs_manual_grading(self):
    try:
        gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
        subm = gb.find_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
        flag = subm.needs_manual_grade
    finally:
        gb.close()
    return flag



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












class Submission:

    def __init__(self, asgn, stu, grade_uploaded, grade_posted, config):
        self.asgn = asgn
        self.stu = stu
        self.due_date, override = asgn.get_due_date(stu)
        self.snap_name = asgn.name if (override is None) else (asgn.name + '-override-' + override['id'])
        self.grader_folder_root = config.user_folder_root
        self.student_folder_root = config.student_folder_root
        self.student_local_assignment_folder = config.student_local_assignment_folder
        self.student_prefix = 'student_'
        self.snapped_assignment_path = os.path.join(self.student_folder_root, self.stu.canvas_id, '.zfs', 'snapshot', self.snap_name, self.student_local_assignment_folder, self.asgn.name, self.asgn.name+'.ipynb')
        self.grader_local_collection_folder = os.path.join('submitted', self.student_prefix + self.stu.canvas_id, self.asgn.name)
        self.grader_local_autograded_folder = os.path.join('autograded', self.student_prefix + self.stu.canvas_id, self.asgn.name)
        self.grader_local_feedback_folder = os.path.join('feedback', self.student_prefix + self.stu.canvas_id, self.asgn.name)
        self.grader = self.get_grader()
        self.grader_repo_path = None
        self.grade_uploaded = grade_uploaded
        self.grade_posted = grade_posted
        self.autograde_docker_job_id = None
        self.feedback_docker_job_id = None
        self.score = None
        self.max_score = None
        self.error = None

    def get_grader(self):
        graders = [username.strip('/') for username in os.listdir(self.grader_folder_root) if self.asgn.grader_basename() in username]
        grader = None
        for grd in graders:
            #check if this grader already has this submission
            fldr = os.path.join(self.grader_folder_root, grd, self.grader_local_collection_folder)
            if os.path.exists(fldr) and grader is None:
                grader = grd
            elif os.path.exists(fldr):
                raise MultipleGraderError('Submission ' + self.asgn.name + ' -- ' + self.stu.canvas_id + ' -- has multiple graders: ' + str(grader) + ' and ' + str(grd))
        return grader

    ######################################################
    ###    Funcs to prepare the submission for grading  ##
    ######################################################

    def prepare(self, tz):
        fmt = 'ddd YYYY-MM-DD HH:mm:ss'
        print('Preparing submission ' + self.asgn.name+':'+self.stu.canvas_id)

        #assign the submission to a grader
        print('Assigning submission to grader') 
        try:
            self.assign()
        except Exception as e: #TODO make this exception more specific and raise if unknown type
            print('Error when assigning')
            print(e)
            self.error = e
            return SubmissionStatus.ERROR
        print('Submission assigned to grader ' + self.grader)

        #only start the process if an hour has elapsed to give time for snapshots etc
        if self.due_date.add(hours=1) >= plm.now(): 
            print('Submission not yet ready for collection (due+1hr). Due date: ' + self.due_date.in_timezone(tz).format(fmt) + ' Time now: ' + plm.now().in_timezone(tz).format(fmt))
            return SubmissionStatus.NOT_DUE
        print('Submission ready for collection (due+1hr). Due date: ' + self.due_date.in_timezone(tz).format(fmt) + ' Time now: ' + plm.now().in_timezone(tz).format(fmt))

        #create the collected assignment path
        self.collected_assignment_path = os.path.join(self.grader_repo_path, self.grader_local_collection_folder, self.asgn.name + '.ipynb')

        #try to collect the assignment if not already collected
        print('Collecting submission...')
        try:
            self.collect()
        except Exception as e: #TODO make this exception more specific and raise if unknown type
            if "No such file" in str(e):
                print("Student did not submit on time. Assignment missing.")
                return SubmissionStatus.MISSING
            else:
                print('Error when collecting')
                print(e)
                self.error = e
                return SubmissionStatus.ERROR
        else:
            print('Submission collected.')

        # the assignment was not missing.

        # clean the submission
        print('Submission is collected. Cleaning...')
        try:
            self.clean()
        except Exception as e: #TODO make this exception more specific and raise if unknown type
            print('Error when cleaning')
            print(e)
            self.error = e
            return SubmissionStatus.ERROR 
  
        return SubmissionStatus.PREPARED

    def assign(self):
        # if the grader workload dict hasn't been created in the assignment yet, create it
        if len(self.asgn.grader_workloads) == 0:
            graders = [username.strip('/') for username in os.listdir(self.grader_folder_root) if self.asgn.grader_basename() in username]
            for grd in graders:
                self.asgn.grader_workloads[grd] = 0
        # if unknown grader
        if self.grader is None:
            #assign this to the grader with the least work
            min_ct = 1e64
            min_grader = None
            for grd in self.asgn.grader_workloads:
                if self.asgn.grader_workloads[grd] <= min_ct:
                    min_ct = self.asgn.grader_workloads[grd]
                    min_grader = grd
            self.grader = min_grader

            #create the submission folder in the grader account and set permissions
            jupyter_uid = pwd.getpwnam('jupyter').pw_uid
            fldr = os.path.join(self.grader_folder_root, min_grader, self.grader_local_collection_folder)
            os.makedirs(fldr, exist_ok=True)

            #chown everything inside the grader folder root to jupyter/jupyter, moving backwards through the path hierarchy until we reach the grader root folder
            while not os.path.samefile(fldr, os.path.join(self.grader_folder_root, min_grader)):
                os.chown(fldr, jupyter_uid, jupyter_uid)
                fldr = os.path.dirname(fldr)

        #increment the known grader workload by 1
        self.asgn.grader_workloads[self.grader] += 1
        
        #setup convenience path
        self.grader_repo_path = os.path.join(self.grader_folder_root, self.grader)
            
    def collect(self):
        jupyter_uid = pwd.getpwnam('jupyter').pw_uid
        if not os.path.exists(self.collected_assignment_path):
            shutil.copy(self.snapped_assignment_path, self.collected_assignment_path)
            os.chown(self.collected_assignment_path, jupyter_uid, jupyter_uid)
        
    def clean(self):
        #need to check for duplicate cell ids, see
        #https://github.com/jupyter/nbgrader/issues/1083
        
        #open the student's notebook
        f = open(self.collected_assignment_path, 'r')
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
            print('Student ' + self.stu.canvas_id + ' assignment ' + self.asgn.name + ' grader ' + self.grader + ' had a duplicate cell! ID = ' + str(cell_id))
            print('Removing the nbgrader metainfo from that cell to avoid bugs in autograde')
            cell['metadata'].pop('nbgrader', None)
          else:
            cell_ids.add(cell_id)
    
        #write the sanitized notebook back to the submitted folder
        f = open(self.collected_assignment_path, 'w')
        json.dump(nb, f)
        f.close()

    ######################################################
    ###    Funcs to grade the submission for grading    ##
    ######################################################

    def submit_autograding(self, docker):
        # create the autograded assignment file path
        self.autograded_assignment_path = os.path.join(self.grader_repo_path, self.grader_local_autograded_folder)
        self.autograde_fail_flag_path = os.path.join(self.grader_repo_path, 'autograde_failed_'+self.asgn.name+'-'+self.stu.canvas_id)

        print('Autograding submission ' + self.asgn.name+':'+self.stu.canvas_id)

        if os.path.exists(self.autograde_fail_flag_path):
            print('Autograde failed previously. Returning')
            return SubmissionStatus.AUTOGRADE_FAILED_PREVIOUSLY

        if os.path.exists(self.autograded_assignment_path):
            print('Assignment previously autograded & validated.')
            return SubmissionStatus.AUTOGRADED
        else:
            print('Removing old autograding result from DB if it exists')
            try:
                gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
                gb.remove_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
            except MissingEntry as e:
                pass
            finally:
                gb.close()
            print('Submitting job to docker pool for autograding')
            self.autograde_docker_job_id = docker.submit('nbgrader autograde --force --assignment=' + self.asgn.name + ' --student='+self.student_prefix+self.stu.canvas_id, self.grader_repo_path)
            return SubmissionStatus.NEEDS_AUTOGRADE

    def check_grading(self, canvas, docker_results):
        if self.autograde_docker_job_id is not None:
            print('Checking autograding for submission ' + self.asgn.name+':'+self.stu.canvas_id)
            try:
                self.validate_docker_result(self.autograde_docker_job_id, docker_results, self.autograded_assignment_path)
            except DockerError as e:
                print('Autograder failed.')
                print(e.message)
                print(e.docker_output)
                self.error = e
                #create the fail flag file
                with open(self.autograde_fail_flag_path, 'wb') as f:
                    pass
                jupyter_uid = pwd.getpwnam('jupyter').pw_uid
                os.chown(self.autograde_fail_flag_path, jupyter_uid, jupyter_uid)
                return SubmissionStatus.AUTOGRADE_FAILED
            print('Valid autograder result.')
            self.autograde_docker_job_id = None
            
        # check if the submission needs manual grading
        print('Checking whether submission ' + self.asgn.name+':'+self.stu.canvas_id + ' needs manual grading')
        try:
            if self.needs_manual_grading():
                print('Still needs manual grading.') 
                return SubmissionStatus.NEEDS_MANUAL_GRADE
        except Exception as e:
            print('Error when checking whether subm needs manual grading')
            print(e)
            self.error =e
            return SubmissionStatus.ERROR
            
        print('Done grading for ' + self.asgn.name+':'+self.stu.canvas_id )
        return SubmissionStatus.DONE_GRADING

    def needs_manual_grading(self):
        try:
            gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
            subm = gb.find_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
            flag = subm.needs_manual_grade
        finally:
            gb.close()
        return flag

    ######################################################
    ###    Functions to upload grades to canvas         ##
    ######################################################

    def upload_grade(self, canvas, failed = False):

        if self.grade_uploaded:
            print('Grade already uploaded. Returning')
            return SubmissionStatus.GRADE_UPLOADED

        print('Uploading grade for submission ' + self.asgn.name+':'+self.stu.canvas_id)
        if failed:
            score = 0
        else:
            try:
                gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
                subm = gb.find_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
                score = subm.score
            except Exception as e:
                print('Error when accessing grade from gradebook db')
                print(e)
                self.error = e
                return SubmissionStatus.ERROR
            finally:
                gb.close()

        try:
            max_score = self.compute_max_score()
        except Exception as e:
            print('Error when trying to compute max score from release notebook')
            print(e)
            self.error = e
            return SubmissionStatus.ERROR

        self.score = score
        self.max_score = max_score
        pct = "{:.2f}".format(100*score/max_score)
    
        print('Student ' + self.stu.canvas_id + ' assignment ' + self.asgn.name + ' score: ' + str(score) + (' [HARDFAIL]' if failed else ''))
        print('Assignment ' + self.asgn.name + ' max score: ' + str(max_score))
        print('Pct Score: ' + pct)
        print('Posting to canvas...')
        try:
            canvas.put_grade(self.asgn.canvas_id, self.stu.canvas_id, pct)
        except GradeNotUploadedError as e: 
            print('Error when uploading grade')
            print(e.message)
            self.error = e
            return SubmissionStatus.ERROR
        self.grade_uploaded = True
        return SubmissionStatus.GRADE_UPLOADED

    def compute_max_score(self):
      #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
      #let's compute the max_score from the notebook manually then....
      release_nb_path = os.path.join(self.grader_repo_path, 'release', self.asgn.name, self.asgn.name+'.ipynb')
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

    def finalize_failed_submission(self, canvas):
        print('Uploading 0 for missing submission ' + self.asgn.name+':'+self.stu.canvas_id)
        ret = self.upload_grade(canvas, failed=True)
        if ret == SubmissionStatus.GRADE_UPLOADED:
            self.grade_uploaded = True
        return ret
        
    ######################################################
    ###        Functions to generate feedback           ##
    ######################################################

    def submit_genfeedback(self, docker):
        # create the autograded assignment file path
        self.feedback_path = os.path.join(self.grader_repo_path, self.grader_local_feedback_folder)
        self.feedback_fail_flag_path = os.path.join(self.grader_repo_path, 'feedback_failed_'+self.asgn.name+'-'+self.stu.canvas_id)

        print('Generating feedback for submission ' + self.asgn.name+':'+self.stu.canvas_id)

        if os.path.exists(self.feedback_fail_flag_path):
            print('Feedback failed previously. Returning')
            return SubmissionStatus.FEEDBACK_FAILED_PREVIOUSLY

        if os.path.exists(self.feedback_path):
            print('Feedback previously generated and validated.')
            return SubmissionStatus.FEEDBACK_GENERATED
        else:
            print('Submitting job to docker pool for feedback gen')
            self.feedback_docker_job_id = docker.submit('nbgrader generate_feedback --force --assignment=' + self.asgn.name + ' --student=' + self.student_prefix+self.stu.canvas_id, self.grader_repo_path)
            return SubmissionStatus.NEEDS_FEEDBACK

    def check_feedback(self, docker_results):
        if self.feedback_docker_job_id is not None:
            print('Checking feedback for submission ' + self.asgn.name+':'+self.stu.canvas_id)
            try:
                self.validate_docker_result(self.feedback_docker_job_id, docker_results, self.feedback_path)
            except DockerError as e:
                print('Feedback generation failed.')
                print(e.message)
                print(e.docker_output)
                self.error = e
                #create the fail flag file
                with open(self.feedback_fail_flag_path, 'wb') as f:
                    pass
                jupyter_uid = pwd.getpwnam('jupyter').pw_uid
                os.chown(self.feedback_fail_flag_path, jupyter_uid, jupyter_uid)
                return SubmissionStatus.FEEDBACK_FAILED
            print('Valid feedback generated.')
            self.feedback_docker_job_id = None

        return SubmissionStatus.FEEDBACK_GENERATED

    ######################################################
    ###            Miscellaneous functions              ##
    ######################################################
            
    def validate_docker_result(self, job_id, results, check_path):
        res = results[job_id]
        if 'ERROR' in res['log']:
            raise DockerError('Docker error processing assignment ' + self.asgn.name + ' for student ' + self.stu.canvas_id + ' in grader folder ' + self.grader +'. Exit status ' + res['exit_status'], res['log'])
        if not os.path.exists(check_path):
            raise DockerError('Docker error processing assignment ' + self.asgn.name + ' for student ' + self.stu.canvas_id + ' in grader folder ' + self.grader +'. Docker did not generate expected file at ' + check_path, res['log'])

    def return_feedback(self):
        print('Returning feedback for submission ' + self.asgn.name+':'+self.stu.canvas_id)
        fdbk_path_grader = os.path.join(self.feedback_path, self.asgn.name + '.html')
        fdbk_folder_student = os.path.join(self.student_folder_root, self.stu.canvas_id)
        fdbk_path_student = os.path.join(fdbk_folder_student, self.asgn.name + '_feedback.html')
        if not os.path.exists(fdbk_path_student):
            if os.path.exists(fdbk_folder_student):
                try:
                    shutil.copy(fdbk_path_grader, fdbk_path_student) 
                    jupyter_uid = pwd.getpwnam('jupyter').pw_uid
                    os.chown(fdbk_path_student, jupyter_uid, jupyter_uid)
                except Exception as e:
                    print('Error occured when returning feedback.')
                    print(e)
                    self.error = e
                    return SubmissionStatus.ERROR
            else:
                print('Warning: student folder ' + str(fdbk_folder_student) + ' doesnt exist. Skipping feedback return.')

    def return_solution(self):
        print('Returning solution for submission ' + self.asgn.name+':'+self.stu.canvas_id)
        soln_path_grader = os.path.join(self.grader_repo_path, self.asgn.name + '_solution.html')
        soln_folder_student = os.path.join(self.student_folder_root, self.stu.canvas_id)
        soln_path_student = os.path.join(soln_folder_student, self.asgn.name + '_solution.html')
        if not os.path.exists(soln_path_student):
            if os.path.exists(soln_folder_student):
                try:
                    shutil.copy(soln_path_grader, soln_path_student) 
                    jupyter_uid = pwd.getpwnam('jupyter').pw_uid
                    os.chown(soln_path_student, jupyter_uid, jupyter_uid)
                except Exception as e:
                    print('Error occurred when returning soln.')
                    print(e)
                    self.error = e
                    return SubmissionStatus.ERROR
            else:
                print('Warning: student folder ' + str(soln_folder_student) + ' doesnt exist. Skipping solution return.')



class MultipleGraderError(Exception):
    def __init__(self, message):
        self.message = message


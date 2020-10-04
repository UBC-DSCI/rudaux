from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool
from enum import IntEnum
import os, shutil, pwd
import json
from nbgrader.api import Gradebook, MissingEntry
from .docker import DockerError
from .canvas import GradeNotUploadedError
import pendulum as plm

class SubmissionStatus(IntEnum):
    ERROR = 0
    NOT_DUE = 1
    MISSING = 2
    PREPARED = 3
    NEEDS_AUTOGRADE = 4
    AUTOGRADED = 5
    AUTOGRADE_FAILED_PREVIOUSLY = 6
    AUTOGRADE_FAILED = 7
    NEEDS_MANUAL_GRADE = 8
    DONE_GRADING = 9
    GRADE_UPLOADED = 10
    NEEDS_FEEDBACK = 11
    FEEDBACK_GENERATED = 12
    FEEDBACK_FAILED_PREVIOUSLY = 13
    FEEDBACK_FAILED = 14
    NEEDS_POST = 15
    DONE = 16

class MultipleGraderError(Exception):
    def __init__(self, message):
        self.message = message

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

from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool
from enum import IntEnum
import os, shutil, pwd
import json
from nbgrader.api import Gradebook, MissingEntry
from .docker import DockerError

class SubmissionStatus(IntEnum):
    ASSIGNED = 0
    COLLECTED = 1
    CLEANED = 2
    AUTOGRADED = 3
    NEEDS_MANUAL_GRADING = 4
    GRADED = 5
    FEEDBACK_GENERATED = 6
    GRADE_UPLOADED = 7
    GRADE_POSTED = 8
    FEEDBACK_RETURNED = 9

class Submission:

    def __init__(self, asgn, stu, grader, config):
        self.s_id = stu.canvas_id
        self.a_id = asgn.canvas_id
        self.s_name = stu.name
        self.a_name = asgn.name
        self.update_due(asgn, stu)
        self.grader = grader
        self.status = SubmissionStatus.ASSIGNED
        self.error = None
        self.solution_returned = False
        self.solution_return_error = None
        self.grader_repo_path = os.path.join(config.user_folder_root, grader, config.instructor_repo_name)
        self.student_folder_root = config.student_folder_root
        self.assignment_snap_path = None
        self.submission_path = None
        self.student_prefix = 'student_'

    def update_due(self, asgn, stu):
        self.due_date, override = asgn.get_due_date(stu)
        self.snap_name = a.name if (override is None) else (a.name + '-override-' + override['id'])

    def collect(self):
        self.assignment_snap_path = os.path.join(self.student_folder_root, self.s_id, '.zfs', 'snapshot', self.snap_name, 'dsci-100/materials', self.a_name, self.a_name+'.ipynb')
        submission_folder = os.path.join(self.grader_repo_path, 'submitted', self.student_prefix + self.s_id, self.a_name)
        self.submission_path = os.path.join(submission_folder, self.a_name+'.ipynb')
        shutil.copy(self.assignment_snap_path, self.submission_path) 
        jupyter_uid = pwd.getpwnam('jupyter').pw_uid
        os.chown(self.submission_path, jupyter_uid, jupyter_uid)
        
    def clean(self):
        #need to check for duplicate cell ids, see
        #https://github.com/jupyter/nbgrader/issues/1083
        
        #open the student's notebook
        f = open(self.submission_path, 'r')
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
            print('Student ' + self.s_id + ' assignment ' + self.a_name + ' grader ' + self.grader + ' had a duplicate cell! ID = ' + str(cell_id))
            print('Removing the nbgrader metainfo from that cell to avoid bugs in autograde')
            cell['metadata'].pop('nbgrader', None)
          else:
            cell_ids.add(cell_id)
    
        #write the sanitized notebook back to the submitted folder
        f = open(self.submission_path, 'w')
        json.dump(nb, f)
        f.close()

    def return_solution(self):
        soln_path_grader = os.path.join(self.grader_repo_path, self.a_name + '.html')
        soln_path_student = os.path.join(self.student_folder_root, self.s_id, 'dsci-100/materials', self.a_name, self.a_name + '_soln.html')
        shutil.copy(soln_path_grader, soln_path_student) 
        jupyter_uid = pwd.getpwnam('jupyter').pw_uid
        os.chown(soln_path_student, jupyter_uid, jupyter_uid)

    def submit_autograde(self, docker):
        self.docker_job_id = docker.submit('nbgrader autograde --assignment=' + self.a_name + ' --student='+self.student_prefix+self.s_id, self.grader_repo_path)
  
    def validate_autograde(self, results):
        res = results[self.docker_job_id]
        if 'ERROR' in res['log']:
            raise DockerError('Error autograding assignment ' + self.a_name + ' for student ' + self.s_id + ' in grader folder ' + self.grader + ' at repo path ' + self.grader_repo_path + '. Exit status ' + res['exit_status'], res['log'])

    def needs_manual_grading(self):
        try:
            gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
            subm = gb.find_submission(self.a_name, self.student_prefix+self.s_id)
            flag = subm.needs_manual_grade
        finally:
            gb.close()
        return flag

    def submit_generate_feedback(self, docker): 
        docker.submit('nbgrader generate_feedback --force --assignment=' + self.a_name + ' --student=' + self.student_prefix+self.s_id, self.grader_repo_path)
    
    def validate_feedback(self, results): 
        if 'ERROR' in res['log']:
            raise DockerError('Error generating feedback for ' + self.a_name + ' for student ' + self.s_id + ' in grader folder ' + self.grader + ' at repo path ' + self.grader_repo_path + '. Exit status ' + res['exit_status'], res['log'])


    def return_feedback(self):
        fdbk_path_grader = os.path.join(self.grader_repo_path, 'feedback', self.student_prefix+self.s_id, self.a_name, self.a_name + '.html')
        fdbk_path_student = os.path.join(self.student_folder_root, self.s_id, 'dsci-100/materials', self.a_name, self.a_name + '_feedback.html')
        shutil.copy(fdbk_path_grader, fdbk_path_student) 
        jupyter_uid = pwd.getpwnam('jupyter').pw_uid
        os.chown(fdbk_path_student, jupyter_uid, jupyter_uid)

    def upload_grade(self, canvas):
        try:
            gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
            subm = gb.find_submission(self.a_name, self.student_prefix+self.s_id)
            score = subm.score
        finally:
            gb.close()

        max_score = self.compute_max_score()
    
        print('Student ' + self.s_id + ' assignment ' + self.a_name + ' score: ' + str(score))
        print('Assignment ' + self.a_name + ' max score: ' + str(max_score))
        print('Pct Score: ' + str(100*score/max_score))
        print('Posting to canvas...')
        canvas.put_grade(self.a_id, self.s_id, str(100*score/max_score))

    def compute_max_score(self):
      #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
      #let's compute the max_score from the notebook manually then....
      release_nb_path = os.path.join(self.grader_repo_path, 'release', self.a_name, self.a_name+'.ipynb')
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

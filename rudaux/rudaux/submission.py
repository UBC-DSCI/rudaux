from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool

class Submission:
    # Class Attributes ?
        #TODO
        #shared path goes here
        student_base_path = "/Users/daisymengxi/Dropbox/0-DSCI/DSCI100-test/snapshots"
        student_submission_path = student_base_path+""

        grader_base_path = "/Users/daisymengxi/Dropbox/0-DSCI/DSCI100-test/"
        grader_submission_path = grader_base_path + ""

        status = 'submitted, cleaned, autograded, manual graded, feedback generated, solution, grade posted'

    # Instance Attributes
def __init__(self, stud, assgmt):
        self.student = stud
        self.grader = ""
        self.assigment = assgmt
        self.path = "" #studentnumber-YYYY-MM-DD-HHMM

        self.is_collected = False    #is the submission collected by the TA to their directory?
        self.is_graded = False       #is the submission graded?
        self.is_grade_posted = False  #is grade posted?
        self.is_late = False         #is the submission late?
        self.is_error = False        #some error associated with this submission

        # Flags for various errors accumulated as the workflow script runs
        self.is_assignment_error = False
        self.is_script_error     = False
        self.is_docker_error     = False
        self.error_msg           = []

 
    #copy student snapshot to grader folder
    


def check_submission_exists(course, anm, stu, grader):
  submitted_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.ipynb')
  return os.path.exists(submitted_path)



#need this function to deal with github issue 
#https://github.com/jupyter/nbgrader/issues/1083
def remove_duplicate_grade_ids(course, anm, stu, grader):
  submitted_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.ipynb')
  #open the student's notebook
  f = open(submitted_path, 'r')
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
      print('Student ' + stu + ' assignment ' + anm + ' grader ' + grader + ' had a duplicate cell! ID = ' + str(cell_id))
      print('Removing the nbgrader metainfo from that cell to avoid bugs in autograde')
      cell['metadata'].pop('nbgrader', None)
    else:
      cell_ids.add(cell_id)

  #write the sanitized notebook back to the submitted folder
  f = open(submitted_path, 'w')
  json.dump(nb, f)
  f.close()



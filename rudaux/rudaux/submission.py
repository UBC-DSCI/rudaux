from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool

class Submission:

    def __init__(self, student_canvas_id, assignment_name):
        self.s_id = student_canvas_id
        self.a_name = assignment_name
        self.path = None
        self.grader = None
        
        self.status = 'assigned, collected, cleaned, autograded, manual graded, feedback generated, grade posted, feedback returned, solution returned'
        self.error = None

    def run_workflow(self):
        pass

    def generate_assignment(self):
        pass

    def collect(self):
        pass

    def clean(self):
        pass

    def autograde(self):
        pass
 
    def needs_manual_grading(self):
        pass
 
    def is_manual_grading_done(self):
        pass
 
    def generate_feedback(self): 

    
 
    def autograde(self):
        pass

 
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



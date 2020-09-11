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



def check_needs_manual_grading(course, anm, stu, grader):
  gradebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'],
                                      course['gradebook_filename'])
  gb = Gradebook('sqlite:///'+gradebook_file)

  try:
    subm = gb.find_submission(anm, course['student_name_prefix']+stu)
    flag = subm.needs_manual_grade
  except MissingEntry as e:
    print(e)
  finally:
    gb.close()

  return flag

def upload_grade(course, anm, stu, grader):
  print('Getting grade for student ' + stu + ' assignment ' + anm)
  course_dir_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])

  gradebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'],
                                      course['gradebook_filename'])
  gb = Gradebook('sqlite:///'+gradebook_file)

  try:
    subm = gb.find_submission(anm, course['student_name_prefix']+stu)
    score = subm.score
  except MissingEntry as e:
    print(e)
  finally:
    gb.close()
  max_score = compute_max_score(course, anm, grader)

  print('Student ' + stu + ' assignment ' + anm + ' score: ' + str(score))
  print('Assignment ' + anm + ' max score: ' + str(max_score))
  print('Pct Score: ' + str(100*score/max_score))
  print('Posting to canvas...')
  canvas.post_grade(course, anm, stu, str(100*score/max_score))

def compute_max_score(course, anm, grader):
  #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
  #let's compute the max_score from the notebook manually then....

  release_notebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_release_path'],
                                      anm,
                                      anm+'.ipynb')
  f = open(release_notebook_file, 'r')
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




       
        ##create the local path 
        #local_repo_path = os.path.join(course['course_storage_path'], 
        #                                    grader,
        #                                    course['instructor_repo_path'])

        #print('Running a docker container to check if assignment ' + anm + ' exists for ' + grader)
        #docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader db assignment list'
        #print(docker_command)
        #result = str(subprocess.check_output(docker_command.split(' ')))
        #print('Result:')
        #print(result)
        #if anm not in result:
        #  print('Need to generate assignment ' + anm + ' for grader ' + grader)
        #  docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader generate_assignment --force ' + anm
        #  print(docker_command)
        #  subprocess.check_output(docker_command.split(' '))



import docker

class DockerGrader(object):

    def __init__(self, course):
        self.client = docker.from_env()
        self.image = 'ubc-dsci/r-dsci-grading:v0.11.0'
        self.jupyterhub_config_dir = course.config.jupyterhub_config_dir
        self.jupyterhub_user_folder_root = course.config.jupyterhub_user_folder_root
        self.assignment_folder_root = course.config.assignment_folder_root
        self.dry_run = course.dry_run

        
    def _run(self, command):
        return self.client.containers.run(self.image, 'command',
                   detach = True, 
                   remove = False,
                   stderr = True,
                   stdout = True,
                   mem_limit = '2g',
                   volumes = {'local_repo_path' : {'bind': '/home/jupyter', 'mode': 'rw'}}
                   )
    def generate_assignment(self):
        pass

    def autograde(self):
        pass
    
    def generate_feedback(self):
        pass

    def generate_solution(self):
        pass

    def 



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



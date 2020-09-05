import docker

class Docker(object):

    def __init__(self):
        self.docker_client = docker.from_env()



 #create the local path 
  local_repo_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])

  print('Running a docker container to check if assignment ' + anm + ' exists for ' + grader)
  docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader db assignment list'
  print(docker_command)
  result = str(subprocess.check_output(docker_command.split(' ')))
  print('Result:')
  print(result)
  if anm not in result:
    print('Need to generate assignment ' + anm + ' for grader ' + grader)
    docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader generate_assignment --force ' + anm
    print(docker_command)
    subprocess.check_output(docker_command.split(' '))




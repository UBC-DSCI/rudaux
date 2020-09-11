import docker

class DockerGrader(object):

    def __init__(self, course):
        self.client = docker.from_env()
        self.image = 'ubc-dsci/r-dsci-grading:v0.11.0'
        self.jupyterhub_config_dir = course.config.jupyterhub_config_dir
        self.jupyterhub_user_folder_root = course.config.jupyterhub_user_folder_root
        self.assignment_folder_root = course.config.assignment_folder_root
        self.dry_run = course.dry_run

        
    def _run(self, command, detach, timeout):
        #detach, entrypoint, environment, mem_limit, volumes, working_dir, stderr, stdout, timeout (do it from outside the container?), cpu_rt_runtime 
        self.client.containers.run(self.image, 'echo hello world')
        self.client.containers.list()
        ctr = self.client.containers.get('32487rfserw89')
        strout = ctr.logs()        
        ctr.stop()


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

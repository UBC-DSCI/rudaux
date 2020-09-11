import docker

class Docker(object):

    def __init__(self, course):
        self.client = docker.from_env()
        self.image = 'ubc-dsci/r-dsci-grading:v0.11.0'
        self.dry_run = course.dry_run
        self.commands = {}
        self.job_id = 0

    def submit(self, command):
        key = 'job-' + str(self.job_id)
        self.commands[key] = command
        self.job_id += 1
        return key

    def run(self, command):
        result = {}
        ctr = self.client.containers.run(self.image, commands[key],
                                                          detach = False, 
                                                          remove = False,
                                                          stderr = True,
                                                          stdout = True,
                                                          mem_limit = '2g',
                                                          volumes = {'local_repo_path' : {'bind': '/home/jupyter', 'mode': 'rw'}}
                                                          )
        result['exit_status'] = ctr.status
        result['log'] = ctr.logs(stdout = True, stderr = True)
        ctr.remove(v = True, force = True)
        return result

    def run_all(self, nthreads):
        results = {}
        running = {}
        for key in self.commands:
            results[key] = {}
            # sleep while we have reached max threads and all running
            while len(running) >= nthreads and all([running[k].status == 'running' for k in running]):
                sleep(0.25)
            # clean out nonrunning containers
            for k in running:
                if running[k].status != 'running':
                    results[k]['exit_status'] = running[k].status
                    results[k]['log'] = running[k].logs(stdout = True, stderr = True)
                    running[k].remove(v = True, force = True)
                    running.pop(k, None)
            # add a new container
            assert len(running) < nthreads
            try:
                if not self.dry_run:
                    ctr = self.client.containers.run(self.image, self.commands[key],
                                                          detach = True, 
                                                          remove = False,
                                                          stderr = True,
                                                          stdout = True,
                                                          mem_limit = '2g',
                                                          volumes = {'local_repo_path' : {'bind': '/home/jupyter', 'mode': 'rw'}}
                                                          )
                    running[key] = ctr
                else:
                    print('[Dry Run: would have started docker container ' + key + ' with command: ' + commands[key] + ']')
                    results[key]['exit_status'] = 'dry_run'
                    results[key]['log'] = 'dry_run'
            except docker.errors.APIError as e:
                print('Docker APIError exception encountered when starting docker container: ' + str(commands[key]))
                results[key]['exit_status'] = 'never_started'
                results[key]['log'] = str(e)
            except docker.errors.ImageNotFound as e:
                print('Docker ImageNotFound exception encountered when starting docker container: ' + str(commands[key]))
                results[key]['exit_status'] = 'never_started'
                results[key]['log'] = str(e)
            except Exception as e:
                print('Unknown exception encountered when starting docker container: ' + str(commands[key]))
                results[key]['exit_status'] = 'never_started'
                results[key]['log'] = str(e)

        # clear the commands queue when done
        self.commands = {} 

        return results




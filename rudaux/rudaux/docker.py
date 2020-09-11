import docker

class Docker(object):

    def __init__(self, course):
        self.client = docker.from_env()
        self.image = 'ubc-dsci/r-dsci-grading:v0.11.0'
        self.dry_run = course.dry_run

    def run(self, commands, nthreads):
        results = {}
        running = {}
        for key in commands:
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
                    ctr = self.client.containers.run(self.image, commands[key],
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
            
        return results

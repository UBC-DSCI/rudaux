import docker

class Docker(object):

    def __init__(self, course):
        self.client = docker.from_env()
        self.image = 'ubc-dsci/r-dsci-grading:v0.11.0'
        self.dry_run = course.dry_run
        self.jobs = {}
        self.job_id = 0

    def submit(self, command, homedir = None):
        key = 'job-' + str(self.job_id)
        self.jobs[key] = {'command': command, 'homedir' : homedir}
        self.job_id += 1
        return key

    def run(self, command, homedir = None):
        ctr, result = self._run_container(command, homedir)
        if ctr:
            while ctr.status == 'running':
                sleep(0.25)
            result['exit_status'] = ctr.status
            result['log'] = ctr.logs(stdout = True, stderr = True)
            ctr.remove(force = True)
        return result

    def run_all(self, nthreads):
        results = {}
        running = {}
        for key in self.jobs:
            results[key] = {}
            # sleep while we have reached max threads and all running
            while len(running) >= nthreads and all([running[k].status == 'running' for k in running]):
                sleep(0.25)
            # clean out nonrunning containers
            for k in running:
                if running[k].status != 'running':
                    results[k]['exit_status'] = running[k].status
                    results[k]['log'] = running[k].logs(stdout = True, stderr = True)
                    running[k].remove(force = True)
                    running.pop(k, None)
            # add a new container
            assert len(running) < nthreads
            ctr, results[key] = self._run_container(self.jobs[key]['command'], self.jobs[key]['homedir'])
            if ctr:
                running[key] = ctr
        # clear the commands queue when done
        self.jobs = {} 

        return results

    def _run_container(self, command, homedir):
        ctr = None
        result = {}
        try:
            if not self.dry_run:
                ctr = self.client.containers.run(self.image, command,
                                                      detach = True,
                                                      remove = False,
                                                      stderr = True,
                                                      stdout = True,
                                                      mem_limit = '2g',
                                                      volumes = {homedir : {'bind': '/home/jupyter', 'mode': 'rw'}} if homedir else {}
                                                      )
            else:
                print('[Dry Run: would have started docker container ' + key + ' with command: ' + commands[key] + ']')
                result['exit_status'] = 'dry_run'
                result['log'] = 'dry_run'
        except docker.errors.APIError as e:
            print('Docker APIError exception encountered when starting docker container: ' + str(commands[key]))
            result['exit_status'] = 'never_started'
            result['log'] = str(e)
            ctr = None
        except docker.errors.ImageNotFound as e:
            print('Docker ImageNotFound exception encountered when starting docker container: ' + str(commands[key]))
            result['exit_status'] = 'never_started'
            result['log'] = str(e)
            ctr = None
        except Exception as e:
            print('Unknown exception encountered when starting docker container: ' + str(commands[key]))
            result['exit_status'] = 'never_started'
            result['log'] = str(e) 
            ctr = None
        return ctr, result




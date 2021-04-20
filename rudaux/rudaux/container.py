import docker
import time

def run_container(config, command, homedir = None):
    ctr = None
    result = {}
    n_tries = 5
    # try to start the container a few times 
    while ctr is None and n_tries > 0:
        n_tries -= 1
        try:
            #start the container
            ctr = self.client.containers.run(config.grading_docker_image, command,
                                                detach = True,
                                                remove = False,
                                                stderr = True,
                                                stdout = True,
                                                mem_limit = config.grading_docker_memory,
                                                volumes = {homedir : {'bind': config.grading_docker_bind_folder, 'mode': 'rw'}} if homedir else {}
                                             )
        except docker.errors.APIError as e:
            if n_tries == 0:
                print('Docker APIError exception encountered when starting docker container')
                print('Command: ' + command)
                print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Docker APIError, ' + str(e)
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                print('Failed to start container. Attempting again; ' + str(n_tries) + ' attempts remaining.')
        except docker.errors.ImageNotFound as e:
            if n_tries == 0:
                print('Docker ImageNotFound exception encountered when starting docker container')
                print('Command: ' + command)
                print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Docker ImageNotFound, ' + str(e)
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                print('Failed to start container. Attempting again; ' + str(n_tries) + ' attempts remaining.')
        except Exception as e:
            if n_tries == 0:
                print('Unknown exception encountered when starting docker container')
                print('Command: ' + command)
                print('Homedir: ' + homedir)
            result['exit_status'] = 'never_started'
            result['log'] = 'ERROR: Unknown exception, ' + str(e) 
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                print('Failed to start container. Attempting again; ' + str(n_tries) + ' attempts remaining.')
    
    # if the container started successfully, poll until it is finished
    if ctr:
        while ctr.status in ['running', 'created']:
            time.sleep(0.25)
            ctr.reload()
        result['exit_status'] = ctr.status
        result['log'] = ctr.logs(stdout = True, stderr = True).decode('utf-8')
        ctr.remove()
  
    # return the result
    return result



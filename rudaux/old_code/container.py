import docker
import time
from .utilities import get_logger
from prefect.engine import signals

def run_container(config, command, homedir = None):
    client = docker.from_env()
    logger = get_logger()
    ctr = None
    result = {}
    n_tries = 5
    # try to start the container a few times 
    while ctr is None and n_tries > 0:
        n_tries -= 1
        try:
            #start the container
            ctr = client.containers.run(config.docker_image, command,
                                                detach = True,
                                                remove = False,
                                                stderr = True,
                                                stdout = True,
                                                mem_limit = config.docker_memory,
                                                volumes = {homedir : {'bind': config.docker_bind_folder, 'mode': 'rw'}} if homedir else {}
                                             )
        except docker.errors.APIError as e:
            if n_tries == 0:
                raise signals.FAIL(f"Docker APIError exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                logger.info(f"Docker APIError exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
                logger.info(f"Failed to start container. Attempting again; {n_tries} attempts remaining.")
        except docker.errors.ImageNotFound as e:
            if n_tries == 0:
                raise signals.FAIL(f"Docker ImageNotFound exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                logger.info(f"Docker ImageNotFound exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
                logger.info(f"Failed to start container. Attempting again; {n_tries} attempts remaining.")
        except Exception as e:
            if n_tries == 0:
                raise signals.FAIL(f"Docker unknown exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                logger.info(f"Docker unknown exception encountered when starting docker container. command {command} homedir {homedir}. error message {str(e)}")
                logger.info(f"Failed to start container. Attempting again; {n_tries} attempts remaining.")
    
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



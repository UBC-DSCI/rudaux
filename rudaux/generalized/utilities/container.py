import docker
import time
from .utilities import get_logger

def run_container(command, docker_image, docker_memory = '2g', work_dir = None, ctr_bind_dir = None, n_tries = 5):
    client = docker.from_env()
    logger = get_logger()
    ctr = None
    result = {}
    # try to start the container a few times
    while ctr is None and n_tries > 0:
        n_tries -= 1
        try:
            #start the container
            ctr = client.containers.run(docker_image, command,
                                                detach = True,
                                                remove = False,
                                                stderr = True,
                                                stdout = True,
                                                mem_limit = config.docker_memory,
                                                volumes = {work_dir : {'bind': ctr_bind_dir, 'mode': 'rw'}} if (work_dir and ctr_bind_dir) else {}
                                             )
        except docker.errors.APIError as e:
            if n_tries == 0:
                raise Exception(f"Docker APIError exception encountered when starting docker container. command {command} work_dir {work_dir}. error message {str(e)}")
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                logger.info(f"Docker APIError exception encountered when starting docker container. command {command} work_dir {work_dir}. error message {str(e)}")
                logger.info(f"Failed to start container. Attempting again; {n_tries} attempts remaining.")
        except docker.errors.ImageNotFound as e:
            ctr = None
            raise Exception(f"Docker ImageNotFound exception encountered when starting docker container. image {image_name} command {command} work_dir {work_dir}. error message {str(e)}")
        except Exception as e:
            if n_tries == 0:
                raise Exception(f"Docker unknown exception encountered when starting docker container. command {command} work_dir {work_dir}. error message {str(e)}")
            ctr = None
            time.sleep(10.)
            if n_tries > 0:
                logger.info(f"Docker unknown exception encountered when starting docker container. command {command} work_dir {work_dir}. error message {str(e)}")
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



import os
import paramiko as pmk
import time
from loguru import logger

class SSHUtil:
    # Open an SSH connection to target host
    # TAKES: config, course_section_name, superuser
    # RETURNS: paramiko SSH client
    def ssh_open(self, config, course_section_name, superuser):
        stu_ssh = config[course_section_name]

        max_tries = stu_ssh['max_tries']
        tries = 0

        logger.info(f"Opening ssh connection to {stu_ssh['hostname']}")

        while tries < max_tries:
            try:
                tries += 1

                client = pmk.client.SSHClient()
                client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
                client.load_system_host_keys()
                if superuser:
                    client.connect(stu_ssh['hostname'], stu_ssh['port'], stu_ssh['superuser'], allow_agent=True)
                else:
                    client.connect(stu_ssh['hostname'], stu_ssh['port'], stu_ssh['user'], allow_agent=True)
                s = client.get_transport().open_session()
                pmk.agent.AgentRequestHandler(s)

                return client
            except Exception as e:
                if tries < max_tries:
                    logger.info('Failed to connect to host, trying again...')
                    logger.info(f'Error message: {str(e)}')
                    time.sleep(0.5)
                else:
                    logger.info(f'Failed {tries} times to connect to host.')
                    raise e

    # Copy file from local filesystem to remote host or remote host to local filesystem
    # TAKES: Paramiko client, local file path, remote file path, fromremote=True if copying from remote
    def copy_remote(self, client, localfile, remotefile, fromremote=False):
        sftp_client=client.open_sftp()
        try: 
            if fromremote:
                sftp_client.stat(remotefile)
                sftp_client.get(remotefile, localfile)
            else:
                if not os.path.exists(localfile):
                    raise Exception(f"No such local file {localfile}")
                sftp_client.put(localfile, remotefile)
        except Exception as e:
            logger.info(f"Failed to transfer file {remotefile if fromremote else localfile} {'from' if fromremote else 'to'} remote:\n {e}")
            sftp_client.close()
            raise e
        finally:
            sftp_client.close()

    # Check if file exists on remote host
    # TAKES: Paramiko client, remote file path
    # RETURNS: True if exists, False otherwise
    def file_exists_remote(self, client, remotefile):
        cmd = 'test -f ' + remotefile
        # execute the snapshot command
        stdin, stdout, stderr = client.exec_command(cmd)

        exitstatus = stdout.channel.recv_exit_status()

        return not exitstatus

    # Check if directory exists on remote host
    # TAKES: Paramiko client, remote dir path
    # RETURNS: True if exists, False otherwise
    def dir_exists_remote(self, client, remotedir):
        cmd = 'test -d ' + remotedir
        # execute the snapshot command
        stdin, stdout, stderr = client.exec_command(cmd)

        exitstatus = stdout.channel.recv_exit_status()

        return not exitstatus
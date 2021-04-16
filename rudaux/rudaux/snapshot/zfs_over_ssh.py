from subprocess import check_output, STDOUT
import os
from prefect import task
from prefect.engine import signals
import paramiko as pmk

def validate_config(config):
    # TODO validate these
    config.student_ssh_hostname
    config.student_ssh_port
    config.student_ssh_username
    config.student_zfs_path #usually /usr/sbin/zfs
    config.student_dataset_root 
    return True

def _get_ssh_client(config):
    
    return client

def _snapshot(config, snap_path):
    # open a ssh connection to the student machine
    client = pmk.client.SSHClient()
    client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(config.student_ssh_hostname, config.student_ssh_port, config.student_ssh_username, allow_agent=True)
    s = client.get_transport().open_session()
    pmk.agent.AgentRequestHandler(s)

    # execute the snapshot command
    stdin, stdout, stderr = client.exec_command(config.student_zfs_path + ' snapshot -r ' + snap_path)
    stdout.channel.recv_exit_status()
    stderr.channel.recv_exit_status()
    for line in stdout:
        print('... ' + line.strip('\n'))
    for line in stderr:
        print('... ' + line.strip('\n'))

    # verify the snapshot
    stdin, stdout, stderr = client.exec_command(config.student_zfs_path + ' list -t snapshot')
    stdout.channel.recv_exit_status()
    stderr.channel.recv_exit_status()
    for line in stdout:
        print('... ' + line.strip('\n'))
    for line in stderr:
        print('... ' + line.strip('\n'))
    client.close()

def snapshot_all(config, assignment, snap_name):
    snap_path = config.student_dataset_root.strip('/') + '@' + snap_name
    _snapshot(config, snap_path)

def snapshot_student(config, assignment, student, snap_name):
    snap_path = os.path.join(config.student_datset_root, user['name']).strip('/') + '@' + snap_name
    _snapshot(config, snap_path)

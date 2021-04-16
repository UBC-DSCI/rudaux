from subprocess import check_output, STDOUT
import os
from prefect import task
import paramiko as pmk

def validate_config(config):
    # TODO: make sure the config has everything needed 
    # for this particular snapshot
    return True

def _get_ssh_client(config):
    client = pmk.client.SSHClient()
    client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(host, port, username, allow_agent=True)
    s = client.get_transport().open_session()
    pmk.agent.AgentRequestHandler(s)
    return client

def _snapshot(config, snap_path):
    zfs_path = config.student_zfs_path #usually /usr/sbin/zfs
    client = _get_ssh_client(config)
    stdin, stdout, stderr = client.exec_command(zfs_path + ' snapshot -r ' + snap_path)
    stdout.channel.recv_exit_status()
    stderr.channel.recv_exit_status()
    for line in stdout:
        print('... ' + line.strip('\n'))
    for line in stderr:
        print('... ' + line.strip('\n'))
    # TODO verify the snapshot
    stdin, stdout, stderr = client.exec_command(zfs_path + ' list -t snapshot')
    stdout.channel.recv_exit_status()
    stderr.channel.recv_exit_status()
    for line in stdout:
        print('... ' + line.strip('\n'))
    for line in stderr:
        print('... ' + line.strip('\n'))
    client.close()

def snapshot_all(config, assignment, snap_name):
    snap_path = dataset_root.strip('/') + '@' + snap_name
    _snapshot(config, snap_path)

def snapshot_student(config, assignment, student, snap_name):
    snap_path = os.path.join(datset_root, user['name']).strip('/') + '@' + snap_name
    _snapshot(config, snap_path)

from subprocess import check_output, STDOUT
import os
from prefect import task
from prefect.engine import signals
import paramiko as pmk

def validate_config(config):
    # TODO validate these
    #config.student_ssh_hostname
    #config.student_ssh_port
    #config.student_ssh_username
    #config.student_zfs_path #usually /usr/sbin/zfs
    #config.student_dataset_root 
    logger = prefect.context.get("logger").info("rudaux_config.py valid for ZFS snapshots over SSH")
    return config

def _ssh_open(config):
    # open a ssh connection to the student machine
    client = pmk.client.SSHClient()
    client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(config.student_ssh_hostname, config.student_ssh_port, config.student_ssh_username, allow_agent=True)
    s = client.get_transport().open_session()
    pmk.agent.AgentRequestHandler(s)
    return client

def _ssh_command(client, cmd):
    # execute the snapshot command
    stdin, stdout, stderr = client.exec_command(cmd)
    
    # block on result
    stdout.channel.recv_exit_status()
    stderr.channel.recv_exit_status()

    # return
    return stdout, stderr 

def _ssh_snapshot(config, snap_path):
    # open the connection
    client = _ssh_open(config)

    # execute the snapshot
    stdout, stderr = _ssh_command(client, config.student_zfs_path + ' snapshot -r ' + snap_path)

    # verify the snapshot
    stdout, stderr = _ssh_command(client, config.student_zfs_path + ' list -t snapshot')
    
    # close the connection
    client.close()

@task
def extract_snapshots(config, assignments):
    logger = prefect.context.get("logger")
    snaps = []
    for asgn in assignments:
        snaps.append( {'due_at' : asgn['due_at'], 'name' : asgn['name'], 'user' : None})
        for override in asgn['overrides']:
            for student_id in override['student_ids']:
                snaps.append({'due_at': override['due_at'], 'name' : asgn['name']+'-override-'+override['id'], 'user' : student_id})
    return snaps

@task
def get_existing_snapshots(config):
    logger = prefect.context.get("logger")

    logger.info('Opening ssh connection to ' +str(config.student_ssh_hostname))
    client = _ssh_open(config)

    logger.info('Obtaining a list of previously obtained snapshotsChecking Opening ssh connection to ' +str(config.student_ssh_hostname))
    stdout, stderr = _ssh_command(client, config.student_zfs_path + ' list -t snapshot')

    # look for ...@... and take the part after @ but before spaces
    # E.g.
    # NAME                                                    USED  AVAIL     REFER  MOUNTPOINT
    # tank/home/dsci100@worksheet_01                            0B      -      427K  -
    # tank/home/dsci100/110335@worksheet_11                     0B      -      199M  -
    # tank/home/dsci100/111547@worksheet_01-override-103988     0B      -     57.5M  -
    snap_names = []
    for line in stdout: 
        if '@' in line:
            idx1 = line.find('@')+1
            idx2 = line.find(' ', idx1)
            snap_names.append(line[idx1:idx2])
    return snap_names

@task
def take_snapshot(config, snap, existing_snapshots):
    logger = prefect.context.get("logger")
    snap_deadline = snap['due_at']
    snap_name = snap['name']
    snap_user = snap['user']

    if snap_deadline is None:
         sig = signals.SKIP(f"Snapshot {snap_name} has invalid deadline {snap_deadline}")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig

    if snap_deadline < plm.now():
         sig = signals.SKIP(f"Snapshot {snap_name} has future deadline {snap_deadline}; skipping")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig

    if snap_name in existing_snapshots:
         sig = signals.SKIP(f"Snapshot {snap_name} has already been taken; skipping")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         sig.existing_snapshots = existing_snapshots
         raise sig

    logger.info(f'Snapshot {snap_name} deadline {snap_deadline} is valid, past due, and snap does not already exist; taking snapshot.') 
    if snap_user is None:
        snap_path = config.student_dataset_root.strip('/') + '@' + snap_name
        _ssh_snapshot(config, snap_path)
    else:
        snap_path = os.path.join(config.student_datset_root, snap_user).strip('/') + '@' + snap_name
        _ssh_snapshot(config, snap_path)

    return

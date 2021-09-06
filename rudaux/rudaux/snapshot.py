import os
import prefect
from prefect import task
from prefect.engine import signals
import paramiko as pmk

def _parse_zfs_snap_paths(stdout):
    # look for ...@... and take the part after @ but before spaces
    # E.g.
    # NAME                                                    USED  AVAIL     REFER  MOUNTPOINT
    # tank/home/dsci100@worksheet_01                            0B      -      427K  -
    # tank/home/dsci100/110335@worksheet_11                     0B      -      199M  -
    # tank/home/dsci100/111547@worksheet_01-override-103988     0B      -     57.5M  -
    snap_paths = []
    for line in stdout:
        if '@' in line:
            ridx = line.find(' ')
            snap_paths.append(line[:ridx])
    return snap_paths

def _parse_zfs_snap_names(stdout):
    paths = _parse_zfs_snap_paths(stdout)
    names = []
    for path in paths:
        lidx = path.find('@')+1
        names.append(path[lidx:])
    return names

def _ssh_open(config, course_id):
    stu_ssh = config.student_ssh[course_id]
    # open a ssh connection to the student machine
    client = pmk.client.SSHClient()
    client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(stu_ssh['hostname'], stu_ssh['port'], stu_ssh['user'], allow_agent=True)
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

def _ssh_snapshot(config, course_id, snap_path):
    # open the connection
    client = _ssh_open(config, course_id)

    # execute the snapshot
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' snapshot -r ' + snap_path)

    # verify the snapshot
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' list -t snapshot')
    snap_paths = _parse_zfs_snap_paths(stdout)
    if snap_path not in snap_paths:
        sig = signals.FAIL(f"Failed to take snapshot {snap_path}.")
        sig.snap_path = snap_path
        sig.taken_snaps = snap_paths
        raise sig

    # close the connection
    client.close()

def _ssh_list_snapshot_names(config, course_id):
    # open the connection
    client = _ssh_open(config, course_id)

    # list snapshots
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' list -t snapshot')

    return _parse_zfs_snap_names(stdout)

@task
def validate_config(config):
    # TODO validate these
    #config.student_ssh_hostname
    #config.student_ssh_port
    #config.student_ssh_username
    #config.student_zfs_path #usually /usr/sbin/zfs
    #config.student_dataset_root
    #config.course_start_date

def get_snap_name(config, course_id, assignment, override):
    name = config.course_names[course_id]+'-'+ assignment['name']
    if override is not None:
        name = name + '-' + override['id']
    return name

@task
def extract_snapshots(config, course_id, assignments):
    snaps = []
    for asgn in assignments:
        snaps.append( {'due_at' : asgn['due_at'],
                       'name' : get_snap_name(config, course_id, asgn, None),
                       'student_id' : None})
        for override in asgn['overrides']:
            for student_id in override['student_ids']:
                snaps.append({'due_at': override['due_at'],
                              'name' : get_snap_name(config, course_id, asgn, override),
                              'student_id' : student_id})
    return snaps

@task
def get_existing_snapshots(config, course_id):
    logger = prefect.context.get("logger")
    return _ssh_list_snapshot_names(config, course_id)

@task
def take_snapshot(config, course_info, snap, existing_snap_names):
    logger = prefect.context.get("logger")
    snap_deadline = snap['due_at']
    snap_name = snap['name']
    snap_student = snap['student_id']

    if snap_name in existing_snap_names:
         sig = signals.SKIP(f"Snapshot {snap_name} has already been taken; skipping")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         sig.existing_snap_names = existing_snap_names
         raise sig

    if snap_deadline is None:
         sig = signals.FAIL(f"Snapshot {snap_name} has invalid deadline {snap_deadline}")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig

    if snap_deadline > plm.now():
         sig = signals.SKIP(f"Snapshot {snap_name} has future deadline {snap_deadline}; skipping")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig

    if snap_deadline < course_info['start_at']:
         sig = signals.FAIL(f"Snapshot {snap_name} deadline ({snap_deadline}) prior to the course " +
                             "start ({course_info['start_at']}). This is often because of an old deadline " +
                             "from a copied Canvas course from a previous semester. Please make sure " +
                             "assignment deadlines are all updated to the current semester.")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig


    logger.info(f'Snapshot {snap_name} deadline {snap_deadline} is valid, and snap does not already exist; taking snapshot.')
    if snap_user is None:
        snap_path = config.student_ssh[course_info['id']]['student_root'].strip('/') + '@' + snap_name
        _ssh_snapshot(config, course_info['id'], snap_path)
    else:
        snap_path = os.path.join(config.student_ssh[course_info['id']]['student_root'], snap_student).strip('/') + '@' + snap_name
        _ssh_snapshot(config, course_info['id'], snap_path)

    return

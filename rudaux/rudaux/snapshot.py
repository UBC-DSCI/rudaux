import os
import prefect
from prefect import task
from prefect.engine import signals
import paramiko as pmk
import pendulum as plm

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
    logger = prefect.context.get("logger")
    logger.info(f"Parsing ZFS snapshots:\n{paths}")
    names = []
    for path in paths:
        lidx = path.find('@')+1
        names.append(path[lidx:])
    return names

def _ssh_open(config, course_id):
    logger = prefect.context.get("logger")
    stu_ssh = config.student_ssh[course_id]
    logger.info(f"Opening ssh connection to {stu_ssh}")
    # open a ssh connection to the student machine
    client = pmk.client.SSHClient()
    client.set_missing_host_key_policy(pmk.client.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(stu_ssh['hostname'], stu_ssh['port'], stu_ssh['user'], allow_agent=True)
    s = client.get_transport().open_session()
    pmk.agent.AgentRequestHandler(s)
    # TODO error handling
    return client

def _ssh_command(client, cmd):
    logger = prefect.context.get("logger")
    logger.info(f"Running ssh command {cmd}")
    # execute the snapshot command
    stdin, stdout, stderr = client.exec_command(cmd)

    # block on result
    out_status = stdout.channel.recv_exit_status()
    err_status = stderr.channel.recv_exit_status()

    logger.info(f"Command exit codes: out = {out_status}  err = {err_status}")

    # get output
    stdout_lines = []
    for line in stdout:
        stdout_lines.append(line)
    stdout = stdout_lines

    stderr_lines = []
    for line in stderr:
        stderr_lines.append(line)
    stderr = stderr_lines

    if out_status != 0 or err_status != 0:
        sig = signals.FAIL(f"Paramiko SSH command error: nonzero status.\nstderr\n{stderr}\nstdout\n{stdout}")
        sig.stderr = stderr
        sig.stdout = stdout
        raise sig

    # return
    return stdout, stderr

def _ssh_snapshot(config, course_id, snap_path):
    logger = prefect.context.get("logger")
    logger.info(f"Taking a snapshot for course {course_id} , path {snap_path}")
    # open the connection
    logger.info(f"Opening ssh connection")
    client = _ssh_open(config, course_id)

    # execute the snapshot
    logger.info(f"Taking a snapshot")
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' snapshot -r ' + snap_path)

    # verify the snapshot
    logger.info(f"Verifying the snapshot")
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' list -t snapshot')
    snap_paths = _parse_zfs_snap_paths(stdout)
    if snap_path not in snap_paths:
        sig = signals.FAIL(f"Failed to take snapshot {snap_path}.")
        sig.snap_path = snap_path
        sig.taken_snaps = snap_paths
        raise sig

    # close the connection
    logger.info(f"Closing ssh connection")
    client.close()

def _ssh_list_snapshot_names(config, course_id):
    logger = prefect.context.get("logger")
    # open the connection
    client = _ssh_open(config, course_id)

    # list snapshots
    stdout, stderr = _ssh_command(client, config.student_ssh[course_id]['zfs_path'] + ' list -t snapshot')

    # close the connection
    logger.info(f"Closing ssh connection")
    client.close()

    # parse the output of zfs
    snapnames = _parse_zfs_snap_names(stdout)

    # return the list of unique names
    return list(set(snapnames))

def validate_config(config):
    pass
    # TODO validate these
    #config.student_ssh_hostname
    #config.student_ssh_port
    #config.student_ssh_username
    #config.student_zfs_path #usually /usr/sbin/zfs
    #config.student_dataset_root
    #config.course_start_date

def get_snap_name(config, course_id, assignment, override):
    return config.course_names[course_id]+'-'+assignment['name']+'-' + assignment['id'] + ('' if override is None else '-'+ override['id'])

@task
def get_all_snapshots(config, course_id, assignments):
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
    logger = prefect.context.get("logger")
    logger.info(f"Found {len(snaps)} snapshots to take.")
    logger.info(f"Snapshots: {snaps}")
    return snaps

@task
def get_existing_snapshots(config, course_id):
    existing_snaps = _ssh_list_snapshot_names(config, course_id)
    logger = prefect.context.get("logger")
    logger.info(f"Found {len(existing_snaps)} existing snapshots.")
    logger.info(f"Snapshots: {existing_snaps}")
    return existing_snaps


def generate_take_snapshot_name(config, course_info, snap, existing_snap_names, **kwargs):
    return snap['name']

@task(task_run_name=generate_take_snapshot_name)
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
                            f"start ({course_info['start_at']}). This is often because of an old deadline " +
                            f"from a copied Canvas course from a previous semester. Please make sure " +
                            f"assignment deadlines are all updated to the current semester.")
         sig.snap_name = snap_name
         sig.snap_deadline = snap_deadline
         raise sig

    logger.info(f'Snapshot {snap_name} deadline {snap_deadline} is valid, and snap does not already exist; taking snapshot.')
    if snap_student is None:
        snap_path = config.student_ssh[course_info['id']]['student_root'].strip('/') + '@' + snap_name
        _ssh_snapshot(config, course_info['id'], snap_path)
    else:
        snap_path = os.path.join(config.student_ssh[course_info['id']]['student_root'], snap_student).strip('/') + '@' + snap_name
        _ssh_snapshot(config, course_info['id'], snap_path)
    return

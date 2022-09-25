from prefect import task
# from prefect.engine import signals
from rudaux.util.util import get_logger
from rudaux.model.snapshot import Snapshot
import pendulum as plm


def get_snapshot_name(course_name, assignment, override, student):
    return f"{course_name}-{assignment.name}-{assignment.lms_id}" + (
        "" if override is None else f"-{override.name}-{override.lms_id}")


@task
def get_pastdue_snapshots(course_name, course_info, assignments):
    logger = get_logger()
    pastdue_snaps = []
    for asgn in assignments:
        if asgn.due_at > plm.now():
            logger.info(f"Assignment {asgn.name} has future deadline {asgn.due_at}; skipping snapshot")
        elif asgn.due_at < course_info.start_at:
            logger.info(
                f"Assignment {asgn.name} deadline {asgn.due_at} prior to course start date {course_info.start_at}; "
                f"skipping snapshot")
        else:
            logger.info(f"Assignment {asgn.name} deadline {asgn.due_at} past due; "
                        f"adding snapshot to pastdue list")
            snap_name = get_snapshot_name(course_name, asgn, None, None)
            pastdue_snaps.append(Snapshot(assignment=asgn, override=None, student=None, name=snap_name))
        for over in asgn.overrides:
            if over.due_at > plm.now():
                logger.info(
                    f"Assignment {asgn.name} override {over.name} has future deadline {over.due_at}; "
                    f"skipping snapshot")
            elif over.due_at < course_info.start_at:
                logger.info(
                    f"Assignment {asgn.name} override {over.name} deadline {over.due_at} prior to course "
                    f"start date {course_info.start_at}; skipping snapshot")
            else:
                logger.info(
                    f"Assignment {asgn.name} override {over.name} deadline {over.due_at} past due; "
                    f"adding snapshot to pastdue list")
                for stu in over.students:
                    snap_name = get_snapshot_name(course_name, asgn, over, stu)
                    pastdue_snaps.append(Snapshot(assignment=asgn, override=over, student=stu, name=snap_name))

    return pastdue_snaps


@task
def get_existing_snapshots(subs):
    existing_snaps = subs.get_snapshots()
    logger = get_logger()
    logger.info(f"Found {len(existing_snaps)} existing snapshots.")
    logger.info(f"Snapshots: {[snap.name for snap in existing_snaps]}")
    return existing_snaps


@task
def get_snapshots_to_take(pastdue_snaps, existing_snaps):
    pds_set = set(pastdue_snaps)
    e_set = set(existing_snaps)
    snaps_to_take = list(pds_set - e_set)
    logger = get_logger()
    logger.info(f"Found {len(snaps_to_take)} snapshots to take.")
    logger.info(f"Snapshots: {[snap.name for snap in snaps_to_take]}")
    return snaps_to_take


@task
def take_snapshots(snaps_to_take, subs):
    logger = get_logger()
    for snap in snaps_to_take:
        logger.info(f"Taking snapshot {snap.name}")
        subs.take_snapshot(snap)
    return


@task
def verify_snapshots(snaps_to_take, new_existing_snaps):
    stt_set = set(snaps_to_take)
    ne_set = set(new_existing_snaps)
    remaining_snaps = list(ne_set - stt_set)
    if len(remaining_snaps) > 0:
        # sig.FAIL( f"Error taking snapshots {[snap.name for snap in remaining_snaps]}; do not exist in submission
        # system after snapshot") raise sig
        pass
    return

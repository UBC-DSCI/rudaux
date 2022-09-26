from typing import List
from prefect import task
# from prefect.engine import signals
from rudaux.util.util import get_logger
from rudaux.model.snapshot import Snapshot
import pendulum as plm
from rudaux.model.student import Student
from rudaux.model.override import Override
from rudaux.model.assignment import Assignment
from rudaux.model.course_info import CourseInfo


@task
def get_pastdue_snapshots(course_name: str, course_info: CourseInfo, assignments: List[Assignment]):
    logger = get_logger()
    pastdue_snaps = []
    for assignment in assignments:
        if assignment.due_at > plm.now():
            logger.info(f"Assignment {assignment.name} has future deadline {assignment.due_at}; skipping snapshot")
        elif assignment.due_at < course_info.start_at:
            logger.info(
                f"Assignment {assignment.name} deadline {assignment.due_at} "
                f"prior to course start date {course_info.start_at}; skipping snapshot")
        else:
            logger.info(f"Assignment {assignment.name} deadline {assignment.due_at} "
                        f"past due; adding snapshot to pastdue list")
            pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                          override=None, student=None))

        for over in assignment.overrides:
            if over.due_at > plm.now():
                logger.info(
                    f"Assignment {assignment.name} override {over.name} has future deadline {over.due_at}; "
                    f"skipping snapshot")
            elif over.due_at < course_info.start_at:
                logger.info(
                    f"Assignment {assignment.name} override {over.name} deadline {over.due_at} prior to course "
                    f"start date {course_info.start_at}; skipping snapshot")
            else:
                logger.info(
                    f"Assignment {assignment.name} override {over.name} deadline {over.due_at} past due; "
                    f"adding snapshot to pastdue list")
                for stu in over.students:
                    pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                                  override=over, student=stu))

    return pastdue_snaps


# -----------------------------------------------------------------------------------------------
@task
def get_existing_snapshots(subs):
    existing_snaps = subs.list_snapshots()
    logger = get_logger()
    logger.info(f"Found {len(existing_snaps)} existing snapshots.")
    logger.info(f"Snapshots: {[snap.name for snap in existing_snaps]}")
    return existing_snaps


# -----------------------------------------------------------------------------------------------
@task
def get_snapshots_to_take(pastdue_snaps, existing_snaps):
    pds_set = set(pastdue_snaps)
    e_set = set(existing_snaps)
    snaps_to_take = list(pds_set - e_set)
    logger = get_logger()
    logger.info(f"Found {len(snaps_to_take)} snapshots to take.")
    logger.info(f"Snapshots: {[snap.name for snap in snaps_to_take]}")
    return snaps_to_take


# -----------------------------------------------------------------------------------------------
@task
def take_snapshots(snaps_to_take, subs):
    logger = get_logger()
    for snap in snaps_to_take:
        logger.info(f"Taking snapshot {snap.name}")
        subs.take_snapshot(snap)
    return


# -----------------------------------------------------------------------------------------------
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
# -----------------------------------------------------------------------------------------------

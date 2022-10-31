from typing import List, Dict
from prefect import task, get_run_logger
from prefect.exceptions import PrefectSignal

from rudaux.interface import SubmissionSystem
# from prefect.engine import signals
# from rudaux.util.util import get_logger
from rudaux.model.snapshot import Snapshot
import pendulum as plm
from rudaux.model.student import Student
from rudaux.model.override import Override
from rudaux.model.assignment import Assignment
from rudaux.model.course_info import CourseInfo


@task
def get_pastdue_snapshots(course_name: str, course_info: CourseInfo,
                          assignments: Dict[str, Assignment]) -> Dict[str, Snapshot]:
    """
    returns a dictionary of snapshots which are past their due date

    Parameters
    ----------
    course_name: str
    course_info: CourseInfo
    assignments: Dict[str, Assignment]

    Returns
    -------
    pastdue_snaps: Dict[str, Snapshot]

    """
    logger = get_run_logger()
    pastdue_snaps = dict()

    for assignment_id, assignment in assignments.items():

        # if we are not past the assignment's due date yet, we skip
        if assignment.due_at > plm.now():
            logger.info(f"Assignment {assignment.name} has future deadline {assignment.due_at}; skipping snapshot")

        # if the assignment's due date is before the course's start date, we skip
        elif assignment.due_at < course_info.start_at:
            logger.info(
                f"Assignment {assignment.name} deadline {assignment.due_at} "
                f"prior to course start date {course_info.start_at}; skipping snapshot")

        # if we are past the assignment's due date, and it's after the course's start date,
        # we identify that as a pastdue snapshot
        else:
            logger.info(f"Assignment {assignment.name} deadline {assignment.due_at} "
                        f"past due; adding snapshot to pastdue list")
            snapshot = Snapshot(course_name=course_name, assignment=assignment,
                                override=None, student=None)
            pastdue_snaps[snapshot.get_name()] = snapshot

        for override_id, override in assignment.overrides.items():

            # if we are past the assignment's override's due date, we skip
            if override.due_at > plm.now():
                logger.info(
                    f"Assignment {assignment.name} override {override.name} "
                    f"has future deadline {override.due_at}; skipping snapshot")

            # if the assignment's override's due date is before course's start date, we skip
            elif override.due_at < course_info.start_at:
                logger.info(
                    f"Assignment {assignment.name} override {override.name} "
                    f"deadline {override.due_at} prior to course "
                    f"start date {course_info.start_at}; skipping snapshot")

            # if we are past the assignment's override's due date, and it's after the course's start date,
            # we identify that as a pastdue snapshot
            else:
                logger.info(
                    f"Assignment {assignment.name} override {override.name} deadline {override.due_at} past due; "
                    f"adding snapshot to pastdue list")
                for student_id, student in override.students.items():
                    snapshot = Snapshot(course_name=course_name, assignment=assignment,
                                        override=override, student=student)
                    pastdue_snaps[snapshot.get_name()] = snapshot

    return pastdue_snaps


# -----------------------------------------------------------------------------------------------
@task
def get_existing_snapshots(assignments: Dict[str, Assignment], students: Dict[str, Student],
                           subs: SubmissionSystem) -> Dict[str, Snapshot]:
    """
    returns a dictionary of existing snapshots

    Parameters
    ----------
    assignments: Dict[str, Assignment]
    students: Dict[str, Student]
    subs: SubmissionSystem

    Returns
    -------
    existing_snaps_dict: Dict[str, Snapshot]

    """
    existing_snaps_list = subs.list_snapshots(assignments=assignments, students=students)
    existing_snaps_dict = {snap.get_name(): snap for snap in existing_snaps_list}
    logger = get_run_logger()
    logger.info(f"Found {len(existing_snaps_dict)} existing snapshots.")
    logger.info(f"Snapshots: {list(existing_snaps_dict.keys())}")
    return existing_snaps_dict


# -----------------------------------------------------------------------------------------------
@task
def get_snapshots_to_take(pastdue_snaps: Dict[str, Snapshot],
                          existing_snaps: Dict[str, Snapshot]) -> Dict[str, Snapshot]:
    """

    Parameters
    ----------
    pastdue_snaps
    existing_snaps

    Returns
    -------

    """
    # take any snap in pastdue_snaps that is not already in existing_snaps
    snaps_to_take = {pd_snap_name: pd_snap for pd_snap_name, pd_snap in pastdue_snaps.items()
                     if pd_snap_name not in existing_snaps}

    logger = get_run_logger()
    logger.info(f"Found {len(snaps_to_take)} snapshots to take.")
    logger.info(f"Snapshots: {list(snaps_to_take.keys())}")
    return snaps_to_take


# -----------------------------------------------------------------------------------------------
@task
def take_snapshots(snaps_to_take: Dict[str, Snapshot], subs: SubmissionSystem):
    logger = get_run_logger()
    for snap_name, snap in snaps_to_take.items():
        logger.info(f"Taking snapshot {snap_name}")
        subs.take_snapshot(snap)


# -----------------------------------------------------------------------------------------------
@task
def verify_snapshots(snaps_to_take: Dict[str, Snapshot], new_existing_snaps: Dict[str, Snapshot]):

    missing_snaps = []
    for snap_name, snap in snaps_to_take.items():
        if snap_name not in new_existing_snaps:
            missing_snaps.append(snap_name)
    if len(missing_snaps) > 0:
        logger = get_run_logger()
        logger.info(f"Error taking snapshots; {missing_snaps} do not exist in submission system after snapshot")
        raise PrefectSignal
        # sig.FAIL(f"Error taking snapshots {missing_snaps}; do not exist in submission system after snapshot")

# -----------------------------------------------------------------------------------------------

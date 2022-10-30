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
                          assignments: Dict[str, Assignment]) -> List[Snapshot]:
    """
    returns a list of snapshots which are past their due date

    Parameters
    ----------
    course_name: str
    course_info: CourseInfo
    assignments: Dict[str, Assignment]

    Returns
    -------
    pastdue_snaps: List[Snapshot]

    """
    logger = get_run_logger()
    pastdue_snaps = []

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
            pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                          override=None, student=None))

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
                    pastdue_snaps.append(Snapshot(course_name=course_name, assignment=assignment,
                                                  override=override, student=student))

    return pastdue_snaps


# -----------------------------------------------------------------------------------------------
@task
def get_existing_snapshots(course_name: str, course_info: CourseInfo,
                           assignments: Dict[str, Assignment], students: Dict[str, Student],
                           subs: SubmissionSystem) -> List[Snapshot]:

    existing_snaps = subs.list_snapshots(assignments=assignments, students=students)
    logger = get_run_logger()
    logger.info(f"Found {len(existing_snaps)} existing snapshots.")
    logger.info(f"Snapshots: {[snap.get_name() for snap in existing_snaps]}")
    return existing_snaps


# -----------------------------------------------------------------------------------------------
@task
def get_snapshots_to_take(pastdue_snaps: List[Snapshot], existing_snaps: List[Snapshot]) -> List[Snapshot]:
    pds_set = set(pastdue_snaps)
    e_set = set(existing_snaps)
    snaps_to_take = list(pds_set - e_set)
    logger = get_run_logger()
    logger.info(f"Found {len(snaps_to_take)} snapshots to take.")
    logger.info(f"Snapshots: {[snap.get_name() for snap in snaps_to_take]}")
    return snaps_to_take


# -----------------------------------------------------------------------------------------------
@task
def take_snapshots(snaps_to_take: List[Snapshot], subs: SubmissionSystem):
    logger = get_run_logger()
    for snap in snaps_to_take:
        logger.info(f"Taking snapshot {snap.get_name()}")
        subs.take_snapshot(snap)
    return


# -----------------------------------------------------------------------------------------------
@task
def verify_snapshots(snaps_to_take: List[Snapshot], new_existing_snaps: List[Snapshot]):
    logger = get_run_logger()
    stt_set = set(snaps_to_take)
    ne_set = set(new_existing_snaps)
    remaining_snaps = list(ne_set - stt_set)
    if len(remaining_snaps) > 0:
        logger = get_run_logger()
        logger.info(f"Error taking snapshots {[snap.get_name() for snap in remaining_snaps]}; "
                    f"do not exist in submission system after snapshot")
        raise PrefectSignal
        # sig.FAIL( f"Error taking snapshots {[snap.name for snap in remaining_snaps]}; "
        #           f"do not exist in submission system after snapshot") raise sig
        pass
    return
# -----------------------------------------------------------------------------------------------

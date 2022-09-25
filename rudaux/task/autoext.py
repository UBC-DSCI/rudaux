from typing import List

from prefect import task, unmapped
# from prefect.engine import signals
import pendulum as plm
import prefect
from rudaux.util.util import get_logger
from rudaux.model.course_info import CourseInfo
from rudaux.model.assignment import Assignment
from rudaux.model.student import Student
from rudaux.model.instructor import Instructor
from rudaux.model.submission import Submission
from rudaux.model.override import Override
from rudaux.model.settings import Settings

logger = get_logger()


# ----------------------------------------------------------------------------------------------------------
def _get_due_date(assignment: Assignment, student: Student):
    basic_date = assignment.due_at

    # get overrides for the student
    overrides = [over for over in assignment.overrides if
                 student.lms_id in [student.lms_id for student in over.students] and (over.due_at is not None)]

    # if there was no override, return the basic date
    if len(overrides) == 0:
        return basic_date, None

    # if there was one, get the latest override date
    latest_override = overrides[0]
    for over in overrides:
        if over.due_at > latest_override.due_at:
            latest_override = over

    # return the latest date between the basic and override dates
    if latest_override.due_at > basic_date:
        return latest_override['due_at'], latest_override
    else:
        return basic_date, None


# ----------------------------------------------------------------------------------------------------------
@task(name="generate_latereg_overrides_name")
def get_latereg_overrides(extension_days, subm_set, config):
    logger = get_logger()
    fmt = 'ddd YYYY-MM-DD HH:mm:ss'
    overrides = []
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
        course_info = subm_set[course_name]['course_info']
        tz = course_info['time_zone']

        # skip the assignment if it isn't unlocked yet
        if assignment['unlock_at'] > plm.now():
            # raise signals.SKIP(
            #     f"Assignment {assignment['name']} ({assignment['id']}) unlock date "
            #     f"{assignment['unlock_at']} is in the future. Skipping.")
            pass

        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            regdate = student['reg_date']
            override = subm['override']

            to_remove = None
            to_create = None
            if regdate > assignment['unlock_at'] and assignment['unlock_at'] <= plm.from_format(
                    config.registration_deadline, f'YYYY-MM-DD', tz=config.notify_timezone):
                # the late registration due date
                latereg_date = regdate.add(days=extension_days).in_timezone(tz).end_of('day').set(microsecond=0)
                if latereg_date > subm['due_at']:
                    logger.info(f"Student {student['name']} needs an extension on assignment {assignment['name']}")
                    logger.info(f"Student registration date: {regdate}    Status: {student['status']}")
                    logger.info(
                        f"Assignment unlock: {assignment['unlock_at']}    Assignment deadline: {assignment['due_at']}")
                    logger.info("Current student-specific due date: " + subm['due_at'].in_timezone(tz).format(
                        fmt) + " from override: " + str(True if (override is not None) else False))
                    logger.info('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
                    logger.info('Creating automatic late registration extension.')
                    if override is not None:
                        logger.info("Need to remove old override " + str(override['id']))
                        to_remove = override
                    to_create = {'student_ids': [student['id']],
                                 'due_at': latereg_date,
                                 'lock_at': assignment['lock_at'],
                                 'unlock_at': assignment['unlock_at'],
                                 'title': student['name'] + '-' + assignment['name'] + '-latereg'}
                else:
                    continue
            else:
                continue
            overrides.append((assignment, to_create, to_remove))
    return overrides


# ----------------------------------------------------------------------------------------------------------
@task(name="compute_autoextension_override_updates")
def compute_autoextension_override_updates(settings: Settings, course_name: str, section_name: str,
                                           course_info: CourseInfo, students: List[Student],
                                           assignments: List[Assignment]):
    fmt = 'ddd YYYY-MM-DD HH:mm:ss'
    tz = course_info.time_zone
    registration_deadline = settings.canvas_registration_deadlines[section_name]
    notify_timezone = settings.notify_timezone[course_name]
    extension_days = settings.latereg_extension_days[course_name]
    overrides = []

    for assignment in assignments:

        # skip the assignment if it isn't unlocked yet
        if assignment.unlock_at > plm.now():
            print(f"Assignment {assignment.name} ({assignment.lms_id}) "
                  f"unlock date {assignment.unlock_at} is in the future. Skipping.")

        to_remove = None
        to_create = None

        for student in students:

            due_date, override = _get_due_date(assignment, student)

            if student.reg_date > assignment.unlock_at and assignment.unlock_at <= plm.from_format(
                    registration_deadline, f'YYYY-MM-DD', tz=notify_timezone):

                # the late registration due date
                late_reg_date = student.reg_date.add(days=extension_days).in_timezone(
                    tz=tz).end_of('day').set(microsecond=0)

                if late_reg_date > assignment.due_at:
                    logger.info(f"Student {student.name} needs an extension on assignment {assignment.name}")
                    logger.info(f"Student registration date: {student.reg_date}    Status: {student.status}")
                    logger.info(
                        f"Assignment unlock: {assignment.unlock_at}    Assignment deadline: {assignment.due_at}")
                    logger.info("Current student-specific due date: " + due_date.in_timezone(
                        tz=tz).format(fmt) + " from override: " +
                                str(True if (override is not None) else False))
                    logger.info('Late registration extension date: ' + late_reg_date.in_timezone(tz=tz).format(fmt))
                    logger.info('Creating automatic late registration extension.')

                    if override is not None:
                        logger.info("Need to remove old override " + str(override.lms_id))
                        to_remove = override

                    # to_create = {'student_ids': [student.lms_id],
                    #              'due_at': late_reg_date,
                    #              'lock_at': assignment.lock_at,
                    #              'unlock_at': assignment.unlock_at,
                    #              'title': student.name + '-' + assignment.name + '-latereg'}

                    to_create = Override(lms_id=1, name=f"{student.name}-{assignment.name}-latereg",
                                         due_at=late_reg_date, lock_at=assignment.lock_at,
                                         unlock_at=assignment.unlock_at, students=[student])
                else:
                    continue
            else:
                continue
            overrides.append((assignment, to_create, to_remove))
            return overrides


# ----------------------------------------------------------------------------------------------------------
# @task(name="generate_update_override_name")
# def update_override(config, course_id, override_update_tuple):
#     assignment, to_create, to_remove = override_update_tuple
#     if to_remove is not None:
#         _remove_override(config, course_id, assignment, to_remove)
#     if to_create is not None:
#         _create_override(config, course_id, assignment, to_create)

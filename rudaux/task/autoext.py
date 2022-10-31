from typing import List, Tuple, Dict

from prefect import task, unmapped
# from prefect.engine import signals
import pendulum as plm
import prefect
from rudaux.model.course_info import CourseInfo
from rudaux.model.assignment import Assignment
from rudaux.model.student import Student
from rudaux.model.instructor import Instructor
from rudaux.model.submission import Submission
from rudaux.model.override import Override
from rudaux.model.settings import Settings
from prefect import get_run_logger


# ----------------------------------------------------------------------------------------------------------
def _get_due_date(assignment: Assignment, student: Student) -> Tuple[plm.DateTime, Override or None]:
    """
    gets the due date and the override for the given student and the given assignment

    Parameters
    ----------
    assignment: Assignment
    student: Student

    Returns
    -------
    due_date, override: Tuple[plm.DateTime, Override or None]
    """
    logger = get_run_logger()
    original_assignment_due_date = assignment.due_at

    # raise an exception if student appears in more than one override
    # student x has more than one extension (override), please fix

    # get overrides for the student
    student_overrides = [over for over_id, over in assignment.overrides.items() if
                         student.lms_id in [
                             over_student.lms_id for over_student_id, over_student in over.students.items()
                         ] and (over.due_at is not None)]

    # if student has no override, return the original_assignment_due_date
    if len(student_overrides) == 0:
        return original_assignment_due_date, None

    # if there was one, get the latest override date
    # latest_override = student_overrides[0]
    # for student_override in student_overrides:
    #     if student_override.due_at > latest_override.due_at:
    #         latest_override = student_override
    if len(student_overrides) > 1:
        logger.info(f"Student with lms_id: {student.lms_id} and name: {student.name} has multiple overrides. "
                    f"Please make sure each student has at most 1 override per assignment")
        raise ValueError

    # return the latest date between the original and override dates
    # if latest_override.due_at > original_assignment_due_date:
    return student_overrides[0].due_at, student_overrides[0]
    # else:
    #     return original_assignment_due_date, None


# ----------------------------------------------------------------------------------------------------------
@task(name="compute_autoextension_override_updates")
def compute_autoextension_override_updates(settings: Settings, course_name: str, section_name: str,
                                           course_info: CourseInfo, students: Dict[str, Student],
                                           assignments: Dict[str, Assignment]
                                           ) -> List[Tuple[Assignment, List[Override], List[Override]]]:
    """
    returns the list of tuples each corresponding to an assignments and its overrides to delete and create

    Parameters
    ----------
    settings: Settings
    course_name: str
    section_name: str
    course_info: CourseInfo
    students: List[Assignment]
    assignments: List[Assignment]

    Returns
    -------
    overrides: List[Tuple[Assignment, List[Override], List[Override]]]
    """

    logger = get_run_logger()
    date_logging_format = 'ddd YYYY-MM-DD HH:mm:ss'
    tz = course_info.time_zone
    notify_timezone = settings.notify_timezone[course_name]
    registration_deadline = plm.from_format(
        settings.canvas_registration_deadlines[section_name], f'YYYY-MM-DD', tz=notify_timezone)
    extension_days = settings.latereg_extension_days[course_name]
    overrides = []

    for assignment_id, assignment in assignments.items():

        # skip the assignment if it isn't unlocked yet
        if assignment.unlock_at > plm.now():
            print(f"Assignment {assignment.name} ({assignment.lms_id}) "
                  f"unlock date {assignment.unlock_at} is in the future. Skipping.")
            continue

        overrides_to_remove = []
        overrides_to_create = []

        student_override_pairs_to_remove = []
        # student_override_pairs_to_create = []

        for student_id, student in students.items():

            student_due_date, student_override = _get_due_date(assignment, student)
            # the late registration due date
            student_late_reg_date = student.reg_date.add(days=extension_days).in_timezone(
                tz=tz).end_of('day').set(microsecond=0)

            if student.reg_date > assignment.unlock_at and \
                    assignment.unlock_at <= registration_deadline and \
                    student_late_reg_date > student_due_date:

                print('student.name: ', student.name)
                print(student)
                print('student.reg_date: ', student.reg_date)
                print('assignment.unlock_at: ', assignment.unlock_at)
                print('registration_deadline: ', registration_deadline)
                print('student_late_reg_date: ', student_late_reg_date)

                # if student meets the criteria for an extension override

                # ----------------------------------------------------------------------------------------
                # logging related information
                logger.info(f"Student {student.name} needs an extension on assignment {assignment.name}")
                logger.info(f"Student registration date: {student.reg_date}    Status: {student.status}")
                logger.info(
                    f"Assignment unlock: {assignment.unlock_at}    Assignment deadline: {assignment.due_at}")
                logger.info("Current student-specific due date: " + student_due_date.in_timezone(
                    tz=tz).format(date_logging_format) + " from override: " +
                            str(True if (student_override is not None) else False))
                logger.info('Late registration extension date: ' + student_late_reg_date.in_timezone(
                    tz=tz).format(date_logging_format))
                logger.info('Creating automatic late registration extension.')
                logger.info('\n')
                # ----------------------------------------------------------------------------------------

                if student_override is not None:
                    # if student has an override already, the old override needs to be removed
                    logger.info("Need to remove old override " + str(student_override.lms_id))
                    # append the student override to list of overrides to remove
                    overrides_to_remove.append(student_override)
                    # print('override added to be removed', student_override)
                    # append the student-override pair to the student_override_pairs_to_remove
                    student_override_pairs_to_remove.append((student, student_override))

                # create an override for the student and add it to the list override_to_create_for_student
                override_to_create_for_student = Override(
                    lms_id=-1, name=f"{student.name}-{assignment.name}-latereg",
                    due_at=student_late_reg_date, lock_at=assignment.lock_at,
                    unlock_at=assignment.unlock_at, students={student.lms_id: student}
                )
                # print('added override to be created: ', override_to_create_for_student)
                overrides_to_create.append(override_to_create_for_student)
            else:
                # continue to the next student if the criteria is not met
                continue

            # create a dict of students whose overrides need to be removed
            students_with_overrides_to_remove = {student.lms_id: student for student, override in
                                                 student_override_pairs_to_remove}

            # print('students_with_overrides_to_remove: ', students_with_overrides_to_remove)

            for student_with_override_to_remove, override_including_student in student_override_pairs_to_remove:
                # create a dict of students whose overrides should remain (so need to be re-created)
                # students_with_overrides_to_keep =
                #   override_including_student.students - students_with_overrides_to_remove
                students_with_overrides_to_keep = {student_id: student
                                                   for student_id, student in
                                                   override_including_student.students.items()
                                                   if student_id not in students_with_overrides_to_remove}

                # print('students_with_overrides_to_keep: ', students_with_overrides_to_keep)

                if len(students_with_overrides_to_keep) > 0:
                    override_to_create_for_remaining_students = Override(
                        lms_id=override_including_student.lms_id, name=override_including_student.name,
                        due_at=override_including_student.due_at, lock_at=override_including_student.lock_at,
                        unlock_at=override_including_student.unlock_at, students=students_with_overrides_to_keep
                    )
                    overrides_to_create.append(override_to_create_for_remaining_students)

        overrides.append((assignment, overrides_to_create, overrides_to_remove))
        # print('overrides: ', overrides)
    return overrides

# ----------------------------------------------------------------------------------------------------------
# @task(name="generate_update_override_name")
# def update_override(config, course_id, override_update_tuple):
#     assignment, to_create, to_remove = override_update_tuple
#     if to_remove is not None:
#         _remove_override(config, course_id, assignment, to_remove)
#     if to_create is not None:
#         _create_override(config, course_id, assignment, to_create)


# ----------------------------------------------------------------------------------------------------------

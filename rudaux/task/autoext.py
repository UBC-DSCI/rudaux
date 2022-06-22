from prefect import task, unmapped
from prefect.engine import signals
import pendulum as plm
import prefect


@task 
def get_students_assignments(lms):
    stu = lms.get_students()
    asgn = lms.get_assignments()
    return stu, asgn

@task
def validate_student(student)
    return Student(student)

@task
def validate_assignment(assignment)
    return Assignment(assignment)

def _get_due_date(assignment, student):
    basic_date = assignment['due_at']

    #get overrides for the student
    overrides = [over for over in assignment['overrides'] if student['id'] in over['student_ids'] and (over['due_at'] is not None)]

    #if there was no override, return the basic date
    if len(overrides) == 0:
        return basic_date, None

    #if there was one, get the latest override date
    latest_override = overrides[0]
    for over in overrides:
        if over['due_at'] > latest_override['due_at']:
            latest_override = over
    
    #return the latest date between the basic and override dates
    if latest_override['due_at'] > basic_date:
        return latest_override['due_at'], latest_override
    else:
        return basic_date, None

@task
def manage_extensions(config, course_info, submission_pair):
    logger = prefect.context.get("logger")
    tz = course_info['time_zone']
    fmt = 'ddd YYYY-MM-DD HH:mm:ss'
    
    assignment, student = submission_pair

    logger.info(f"Checking if student {student['name']} needs an extension on assignment {assignment['name']}")

    logger.info("Validating assignment due/unlock dates")
    if assignment['unlock_at'] is None or assignment['due_at'] is None:
         sig = signals.FAIL(f"Invalid unlock ({assignment['unlock_at']}) and/or due ({assignment['due_at']}) date for assignment {assignment['name']}")
         sig.assignment = assignment
         raise sig

    logger.info("Validating student registration dates")
    if student['reg_date'] is None:
         sig = signals.FAIL(f"Invalid registration date ({student['reg_date']})")
         sig.student = student
         raise sig

    regdate = student['reg_date']
    logger.info(f"Student registration date: {regdate}    Status: {student['status']}")
    logger.info(f"Assignment unlock: {assignment['unlock_at']}    Assignment deadline: {assignment['due_at']}")
    to_remove = None
    to_create = None
    if student['status'] == 'active' and regdate > assignment['unlock_at']:
        logger.info("Assignment unlock date after student registration date. Extension required.")
        #get their due date w/ no late registration
        due_date, override = _get_due_date(assignment, student)
        logger.info("Current student-specific due date: " + due_date.in_timezone(tz).format(fmt) + " from override: " + str(True if (override is not None) else False))
        #the late registration due date
        latereg_date = regdate.add(days=config.latereg_extension_days)
        logger.info('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
        if latereg_date > due_date:
            logger.info('Creating automatic late registration extension to ' + latereg_date.in_timezone(tz).format(fmt)) 
            if override is not None:
                logger.info("Need to remove old override " + str(override['id']))
                to_remove = override
            to_create = {'student_ids' : [student['id']],
                         'due_at' : latereg_date,
                         'lock_at' : assignment['lock_at'],
                         'unlock_at' : assignment['unlock_at'],
                         'title' : student['name']+'-'+assignment['name']+'-latereg'}
    else:
        logger.info("Student inactive or unlock after registration date; no extension required.")

    return (assignment, to_create, to_remove)

@task(checkpoint=False,task_run_name=generate_latereg_overrides_name)
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
            raise signals.SKIP(f"Assignment {assignment['name']} ({assignment['id']}) unlock date {assignment['unlock_at']} is in the future. Skipping.")

        for subm in subm_set[course_name]['submissions']:
            student = subm['student']
            regdate = student['reg_date']
            override = subm['override']

            to_remove = None
            to_create = None
            if regdate > assignment['unlock_at'] and assignment['unlock_at'] <= plm.from_format(config.registration_deadline, f'YYYY-MM-DD', tz=config.notify_timezone):
                #the late registration due date
                latereg_date = regdate.add(days=extension_days).in_timezone(tz).end_of('day').set(microsecond=0)
                if latereg_date > subm['due_at']:
                    logger.info(f"Student {student['name']} needs an extension on assignment {assignment['name']}")
                    logger.info(f"Student registration date: {regdate}    Status: {student['status']}")
                    logger.info(f"Assignment unlock: {assignment['unlock_at']}    Assignment deadline: {assignment['due_at']}")
                    logger.info("Current student-specific due date: " + subm['due_at'].in_timezone(tz).format(fmt) + " from override: " + str(True if (override is not None) else False))
                    logger.info('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
                    logger.info('Creating automatic late registration extension.')
                    if override is not None:
                        logger.info("Need to remove old override " + str(override['id']))
                        to_remove = override
                    to_create = {'student_ids' : [student['id']],
                                 'due_at' : latereg_date,
                                 'lock_at' : assignment['lock_at'],
                                 'unlock_at' : assignment['unlock_at'],
                                 'title' : student['name']+'-'+assignment['name']+'-latereg'}
                else:
                    continue
            else:
                continue
            overrides.append((assignment, to_create, to_remove))
    return overrides

@task(checkpoint=False,task_run_name=generate_update_override_name)
def update_override(config, course_id, override_update_tuple):
    assignment, to_create, to_remove = override_update_tuple
    if to_remove is not None:
        _remove_override(config, course_id, assignment, to_remove)
    if to_create is not None:
        _create_override(config, course_id, assignment, to_create)



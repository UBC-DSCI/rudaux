import requests
import urllib.parse
import pendulum as plm
from .util import get_logger


########################
# Public API functions
########################

# ----------------------------------------------------------------------------------------------------------------
def get_course_info(api_info, course_id):
    course_info = _get(api_info[course_id], '')[0]
    processed_info = {
        "lms_id": str(course_info['id']),
        "name": course_info['name'],
        "code": course_info['course_code'],
        "start_at": None if course_info['start_at'] is None else plm.parse(course_info['start_at']),
        "end_at": None if course_info['end_at'] is None else plm.parse(course_info['end_at']),
        "time_zone": course_info['time_zone']
    }
    logger = get_logger()
    logger.info(f"Retrieved course info for {course_id}")
    return processed_info


# ----------------------------------------------------------------------------------------------------------------
def get_people(api_info, course_id, enrollment_type):
    people = _get(api_info[course_id], 'enrollments')
    ppl_typ = [p for p in people if p['type'] == enrollment_type]
    ppl = [{'lms_id': str(p['user']['id']),
            'name': p['user']['name'],
            'sortable_name': p['user']['sortable_name'],
            'school_id': str(p['user']['sis_user_id']),
            'reg_date': plm.parse(p['updated_at']) if (plm.parse(p['updated_at']) is not None) else plm.parse(
                p['created_at']),
            'status': p['enrollment_state']
            } for p in ppl_typ
           ]
    logger = get_logger()
    logger.info(f"Retrieved {len(ppl)} students from LMS for {course_id}")
    return ppl


# ----------------------------------------------------------------------------------------------------------------
def get_groups(api_info, course_id):
    grps = _get(api_info[course_id], 'groups')
    logger = get_logger()
    logger.info(f"Retrieved {len(grps)} groups from LMS for {course_id}")
    return [{
        'name': g['name'],
        'lms_id': str(g['id']),
        'members': [str(m['user_id']) for m in
                    _get(api_info[course_id], str(g['id']) + '/memberships', use_group_base=True)]
    } for g in grps]


# ----------------------------------------------------------------------------------------------------------------
def get_assignments(api_info, course_id, assignment_names):
    asgns = _get(api_info[course_id], 'assignments')
    processed_asgns = [{
        'id': str(a['id']),
        'name': a['name'],
        'due_at': None if a['due_at'] is None else plm.parse(a['due_at']),
        'lock_at': None if a['lock_at'] is None else plm.parse(a['lock_at']),
        'unlock_at': None if a['unlock_at'] is None else plm.parse(a['unlock_at']),
        'has_overrides': a['has_overrides'],
        'overrides': [],
        'published': a['published']
    } for a in asgns if a['name'] in assignment_names]

    # fill out overrides
    for a in processed_asgns:
        if a['has_overrides']:
            a['overrides'] = _get_overrides(api_info[course_id], a)

    logger = get_logger()
    logger.info(f"Retrieved {len(processed_asgns)} assignments from LMS for {course_id}")
    # check for duplicate IDs and names
    # we require both of these to be unique (snapshots, grader accounts, etc all depend on unique human-readable names)
    ids = [a['id'] for a in processed_asgns]
    names = [a['name'] for a in processed_asgns]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Course ID {course_id}: Two assignments detected with the same ID. IDs: {ids}")
    if len(set(names)) != len(names):
        raise ValueError(f"Course ID {course_id}: Two assignments detected with the same name. Names: {names}")
    # make sure anything listed in the rudaux_config appears on canvas
    if len(names) < len(assignment_names):
        raise ValueError(
            f"Assignments from config missing in the course LMS.\nConfig: {assignment_names}\nLMS: {names}")

    return processed_asgns


# ----------------------------------------------------------------------------------------------------------------
def get_submissions(api_info, course_id, assignment):
    subms = _get(api_info[course_id], 'assignments/' + assignment['id'] + '/submissions')
    processed_subms = [{
        'student_id': str(subm['user_id']),
        'assignment_id': assignment['id'],
        'score': subm['score'],
        'posted_at': None if subm['posted_at'] is None else plm.parse(subm['posted_at']),
        'late': subm['late'],
        'missing': subm['missing'],
        'excused': subm['excused'],
    } for subm in subms]

    logger = get_logger()
    logger.info(
        f"Retrieved {len(processed_subms)} submissions for assignment {assignment['name']} from LMS for {course_id}")

    subms_map = {}
    for subm in processed_subms:
        if subm['assignment_id'] not in subms_map:
            subms_map[subm['assignment_id']] = {}
        subms_map[subm['assignment_id']][subm['student_id']] = subm
    return subms_map


# ----------------------------------------------------------------------------------------------------------------
def update_grade(api_info, course_id, submission, assignment, student, score):
    # post the grade
    _put(api_info[course_id], 'assignments/' + assignment['id'] + '/submissions/' + student['id'],
         {'submission': {'posted_grade': score}})

    # check that it was posted properly
    canvas_grade = str(
        _get(api_info[course_id], 'assignments/' + assignment['id'] + '/submissions/' + student['id'])[0]['score'])
    if abs(float(score) - float(canvas_grade)) > 0.01:
        raise ValueError(
            f"grade {score} failed to upload for submission {submission['name']} ; grade on canvas is {canvas_grade}")


# ----------------------------------------------------------------------------------------------------------------
def update_extension(api_info, course_id, student, assignment, due_at):
    # find overrides for which student is already a member
    student_overs = []
    for override in assignment['overrides']:
        if student['id'] in override['student_ids']:
            student_overs.append(override)

    # remove from canvas all overrides involving that student
    # and remove the student from the list of ids in each override
    for override in student_overs:
        _remove_override(api_info[course_id], assignment, override)
        override['student_ids'] = filter(lambda x: x != student['id'], override['student_ids'])

    # add a new override for just this student
    student_overs.append({'student_ids': [student['id']],
                          'title': student['name'] + ' ' + assignment['name'],
                          'unlock_at': assignment['unlock_at'],
                          'lock_at': assignment['lock_at'],
                          'due_at': due_at})

    # re-upload all the overrides + new one
    for override in student_overs:
        _create_override(api_info[course_id], assignment, override)


# ----------------------------------------------------------------------------------------------------------------

#################################
# Private Canvas HTTP API functions
#################################

# ----------------------------------------------------------------------------------------------------------------
def _get(api_info, path_suffix, use_group_base=False):
    canvas_domain = api_info['domain']
    course_id = api_info['id']
    token = api_info['token']

    group_url = urllib.parse.urljoin(canvas_domain, 'api/v1/groups/')
    base_url = urllib.parse.urljoin(canvas_domain, 'api/v1/courses/' + course_id + '/')
    if use_group_base:
        url = urllib.parse.urljoin(group_url, path_suffix)
    else:
        url = urllib.parse.urljoin(base_url, path_suffix)

    logger = get_logger()
    logger.info(f"GET request to URL: {url}")

    resp = None
    resp_items = []
    # see https://community.canvaslms.com/t5/Question-Forum/Why-is-the-Assignment-due-at-value-that-of-the-last-override/m-p/209593
    # for why we have to set override_assignment_dates = false below -- basically due_at below gets set
    # really weirdly if the assignment has overrides unless you include this param
    while resp is None or 'next' in resp.links.keys():
        resp = requests.get(
            url=url if resp is None else resp.links['next']['url'],
            headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            },
            json={'per_page': 100},
            params={'override_assignment_dates': False}
        )

        # raise any HTTP errors
        resp.raise_for_status()

        json_data = resp.json()
        if isinstance(json_data, list):
            resp_items.extend(resp.json())
        else:
            resp_items.append(resp.json())
    return resp_items


# ----------------------------------------------------------------------------------------------------------------
def _upload(api_info, path_suffix, json_data, typ):
    canvas_domain = api_info['domain']
    course_id = api_info['id']
    token = api_info['token']

    base_url = urllib.parse.urljoin(canvas_domain, 'api/v1/courses/' + course_id + '/')
    rfuncs = {'put': requests.put,
              'post': requests.post,
              'delete': requests.delete}
    url = urllib.parse.urljoin(base_url, path_suffix)

    logger = get_logger()
    logger.info(f"{typ.upper()} request to URL: {url}")

    resp = rfuncs[typ](
        url=url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        },
        json=json_data
    )

    # raise any HTTP errors
    resp.raise_for_status()
    return


# ----------------------------------------------------------------------------------------------------------------
def _put(api_info, path_suffix, json_data):
    _upload(api_info, path_suffix, json_data, 'put')


# ----------------------------------------------------------------------------------------------------------------
def _post(api_info, path_suffix, json_data):
    _upload(api_info, path_suffix, json_data, 'post')


# ----------------------------------------------------------------------------------------------------------------
def _delete(api_info, path_suffix):
    _upload(api_info, path_suffix, None, 'delete')


# ----------------------------------------------------------------------------------------------------------------
def _get_overrides(api_info, assignment):
    overs = _get(api_info, 'assignments/' + assignment['id'] + '/overrides')
    # print(overs)
    for over in overs:
        over['id'] = str(over['id'])
        over['title'] = str(over['title'])
        if 'student_ids' in over:
            over['student_ids'] = list(map(str, over['student_ids']))
        for key in ['due_at', 'lock_at', 'unlock_at']:
            if over.get(key) is not None:
                over[key] = plm.parse(over[key])
            else:
                over[key] = None
    return overs


# ----------------------------------------------------------------------------------------------------------------
def _create_override(api_info: dict, assignment: dict, override: dict):
    # check all required keys
    required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
    for rk in required_keys:
        if not override.get(rk):
            raise ValueError(
                f"invalid override for assignment {assignment['name']} "
                f"({assignment['id']}): dict missing required key {rk}")

    # convert student ids to integers
    override['student_ids'] = list(map(int, override['student_ids']))

    # convert dates to canvas date time strings in the course local timezone
    for dk in ['unlock_at', 'due_at', 'lock_at']:
        override[dk] = str(override[dk])

    # post the override
    post_json = {'assignment_override': override}
    _post(api_info, 'assignments/' + assignment['id'] + '/overrides', post_json)

    # check that it posted properly
    overs = _get_overrides(api_info, assignment)
    n_match = len([over for over in overs if over['title'] == override['title']])
    if n_match == 0:
        raise ValueError(
            f"override for assignment {assignment['name']} ({assignment['id']}) failed to upload to Canvas")
    if n_match > 1:
        raise ValueError(
            f"multiple overrides for assignment {assignment['name']} "
            f"({assignment['id']}) with title {override['title']} uploaded to Canvas")


# ----------------------------------------------------------------------------------------------------------------
def _remove_override(api_info, assignment, override):
    _delete(api_info, 'assignments/' + assignment['id'] + '/overrides/' + override['id'])

    # check that it was removed properly
    overs = _get_overrides(api_info, assignment)
    n_match = len([over for over in overs if over['id'] == override['id']])
    if n_match != 0:
        raise ValueError(
            f"override {override['title']} for assignment {assignment['name']} "
            f"({assignment['id']}) failed to be removed from Canvas")

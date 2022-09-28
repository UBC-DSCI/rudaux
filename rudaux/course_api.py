import requests
import urllib.parse
import pendulum as plm
import prefect
from prefect import task
from prefect.engine import signals
from .utilities import get_logger

# TODO replace "course api" with "LMS"

def _canvas_get(config, course_id, path_suffix, use_group_base=False):
    group_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/groups/')
    base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+course_id+'/')
    token = config.course_tokens[course_id]

    if use_group_base:
        url = urllib.parse.urljoin(group_url, path_suffix)
    else:
        url = urllib.parse.urljoin(base_url, path_suffix)


    logger = get_logger()
    logger.info(f"GET request to URL: {url}")

    resp = None
    resp_items = []
    #see https://community.canvaslms.com/t5/Question-Forum/Why-is-the-Assignment-due-at-value-that-of-the-last-override/m-p/209593
    #for why we have to set override_assignment_dates = false below -- basically due_at below gets set really weirdly if
    #the assignment has overrides unless you include this param
    while resp is None or 'next' in resp.links.keys():
        resp = requests.get(
            url = url if resp is None else resp.links['next']['url'],
            headers = {
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
                },
            json = {'per_page' : 100},
            params = {'override_assignment_dates' : False}
        )

        if resp.status_code < 200 or resp.status_code > 299:
            sig = signals.FAIL(f"failed GET response status code {resp.status_code} for URL {url}\nText:{resp.text}")
            sig.url = url
            sig.resp = resp
            raise sig

        json_data = resp.json()
        if isinstance(json_data, list):
            resp_items.extend(resp.json())
        else:
            resp_items.append(resp.json())
    return resp_items

def _canvas_upload(config, course_id, path_suffix, json_data, typ):
    base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+course_id+'/')
    token = config.course_tokens[course_id]
    rfuncs = {'put' : requests.put,
             'post': requests.post,
             'delete': requests.delete}
    url = urllib.parse.urljoin(base_url, path_suffix)

    logger = get_logger()
    logger.info(f"{typ.upper()} request to URL: {url}")

    resp = rfuncs[typ](
        url = url,
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
            },
        json=json_data
    )
    if resp.status_code < 200 or resp.status_code > 299:
        sig = signals.FAIL(f"failed upload ({typ}) response status code {resp.status_code} for URL {url}\nText:{resp.text}")
        sig.url = url
        sig.resp = resp
        raise sig
    return

def _canvas_put(config, course_id, path_suffix, json_data):
    _canvas_upload(config, course_id, path_suffix, json_data, 'put')

def _canvas_post(config, course_id, path_suffix, json_data):
    _canvas_upload(config, course_id, path_suffix, json_data, 'post')

def _canvas_delete(config, course_id, path_suffix):
    _canvas_upload(config, course_id, path_suffix, None, 'delete')

def _canvas_get_people_by_type(config, course_id, typ):
    people = _canvas_get(config, course_id, 'enrollments')
    ppl_typ = [p for p in people if p['type'] == typ]
    return [ { 'id' : str(p['user']['id']),
               'name' : p['user']['name'],
               'sortable_name' : p['user']['sortable_name'],
               'school_id' : str(p['user']['sis_user_id']),
               'reg_date' : plm.parse(p['updated_at']) if (plm.parse(p['updated_at']) is not None) else plm.parse(p['created_at']),
               'status' : p['enrollment_state']
              } for p in ppl_typ
           ]

def _canvas_get_overrides(config, course_id, assignment):
    overs = _canvas_get(config, course_id, 'assignments/'+assignment['id']+'/overrides')
    for over in overs:
        over['id'] = str(over['id'])
        over['student_ids'] = list(map(str, over['student_ids']))
        for key in ['due_at', 'lock_at', 'unlock_at']:
            if over.get(key) is not None:
                over[key] = plm.parse(over[key])
            else:
                over[key] = None
    return overs

def _create_override(config, course_id, assignment, override):
    #check all required keys
    required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
    for rk in required_keys:
        if not override.get(rk):
            sig = signals.FAIL(f"invalid override for assignment {assignment['name']} ({assignment['id']}): dict missing required key {rk}")
            sig.assignment = assignment
            sig.override = override
            sig.missing_key = rk
            raise sig

    #convert student ids to integers
    override['student_ids'] = list(map(int, override['student_ids']))

    #convert dates to canvas date time strings in the course local timezone
    for dk in ['unlock_at', 'due_at', 'lock_at']:
        override[dk] = str(override[dk])

    #post the override
    post_json = {'assignment_override' : override}
    _canvas_post(config, course_id, 'assignments/'+assignment['id']+'/overrides', post_json)

    #check that it posted properly
    overs = _canvas_get_overrides(config, course_id, assignment)
    n_match = len([over for over in overs if over['title'] == override['title']])
    if n_match != 1:
        sig = signals.FAIL(f"override for assignment {assignment['name']} ({assignment['id']}) failed to upload to Canvas")
        sig.assignment = assignment
        sig.attempted_override = override
        sig.overrides = overs
        raise sig

def _remove_override(config, course_id, assignment, override):
    _canvas_delete(config, course_id, 'assignments/'+assignment['id']+'/overrides/'+override['id'])

    #check that it was removed properly
    overs = _canvas_get_overrides(config, course_id, assignment)
    n_match = len([over for over in overs if over['id'] == override['id']])
    if n_match != 0:
        sig = signals.FAIL(f"override {override['title']} for assignment {assignment['name']} ({assignment['id']}) failed to be removed from Canvas")
        sig.override = override
        sig.assignment = assignment
        sig.overrides = overs
        raise sig


def validate_config(config):
    pass
    #TODO validate these all strings, format, etc
    #config.canvas_domain
    #config.canvas_token
    #config.canvas_id
    #config.ignored_assignments
    # duplicate assignment names, etc

@task(checkpoint=False)
def get_course_info(config, course_id):
    info = _canvas_get(config, course_id, '')[0]
    processed_info = {
             "id" : str(info['id']),
             "name" : info['name'],
             "code" : info['course_code'],
             "start_at" : None if info['start_at'] is None else plm.parse(info['start_at']),
             "end_at" : None if info['end_at'] is None else plm.parse(info['end_at']),
             "time_zone" : info['time_zone']
    }
    logger = get_logger()
    logger.info(f"Retrieved course info for {config.course_names[course_id]}")
    return processed_info

@task(checkpoint=False)
def get_students(config, course_id):
    ppl = _canvas_get_people_by_type(config, course_id, 'StudentEnrollment')
    logger = get_logger()
    logger.info(f"Retrieved {len(ppl)} students from LMS for {config.course_names[course_id]}")
    return ppl

@task(checkpoint=False)
def get_instructors(config, course_id):
    ppl = _canvas_get_people_by_type(config, course_id, 'TeacherEnrollment')
    logger = get_logger()
    logger.info(f"Retrieved {len(ppl)} instructors from LMS for {config.course_names[course_id]}")
    return ppl

@task(checkpoint=False)
def get_tas(config, course_id):
    ppl = _canvas_get_people_by_type(config, course_id, 'TaEnrollment')
    logger = get_logger()
    logger.info(f"Retrieved {len(ppl)} TAs from LMS for {config.course_names[course_id]}")
    return ppl

@task(checkpoint=False)
def get_groups(config, course_id):
    grps = _canvas_get(config, course_id,'groups')
    logger = get_logger()
    logger.info(f"Retrieved {len(grps)} groups from LMS for {config.course_names[course_id]}")
    return [{
             'name' : g['name'],
             'id' : str(g['id']),
             'members' : [str(m['user_id']) for m in _canvas_get(config, course_id, str(g['id'])+'/memberships', use_group_base=True)]
            } for g in grps]

@task(checkpoint=False)
def get_assignments(config, course_id, assignment_names):
    asgns = _canvas_get(config, course_id, 'assignments')
    processed_asgns = [ {
               'id' : str(a['id']),
               'name' : a['name'],
               'due_at' : None if a['due_at'] is None else plm.parse(a['due_at']),
               'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at']),
               'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at']),
               'has_overrides' : a['has_overrides'],
               'overrides' : [],
               'published' : a['published']
             } for a in asgns if a['name'] in assignment_names]

    # fill out overrides
    for a in processed_asgns:
        if a['has_overrides']:
            a['overrides'] = _canvas_get_overrides(config, course_id, a)

    logger = get_logger()
    logger.info(f"Retrieved {len(processed_asgns)} assignments from LMS for {config.course_names[course_id]}")
    # check for duplicate IDs and names
    # we require both of these to be unique (snapshots, grader accounts, etc all depend on unique human-readable names)
    ids = [a['id'] for a in processed_asgns]
    names = [a['name'] for a in processed_asgns]
    if len(set(ids)) != len(ids):
        sig = signals.FAIL(f"Course ID {course_id}: Two assignments detected with the same ID. IDs: {ids}")
        sig.course_id = course_id
        raise sig
    if len(set(names)) != len(names):
        sig = signals.FAIL(f"Course ID {course_id}: Two assignments detected with the same name. Names: {names}")
        sig.course_id = course_id
        raise sig
    # make sure anything listed in the rudaux_config appears on canvas
    if len(names) < len(assignment_names):
        sig = signals.FAIL(f"Assignments from config missing in the course LMS.\nConfig: {assignment_names}\nLMS: {names}")
        sig.course_id = course_id
        raise sig

    return processed_asgns

def generate_get_submissions_name(config, course_id, assignment, **kwargs):
    return 'get-subms-'+assignment['name']

@task(checkpoint=False,task_run_name=generate_get_submissions_name)
def get_submissions(config, course_id, assignment):
    subms = _canvas_get(config, course_id, 'assignments/'+assignment['id']+'/submissions')
    processed_subms =  [ {
                   'student_id' : str(subm['user_id']),
                   'assignment_id' : assignment['id'],
                   'score' : subm['score'],
                   'posted_at' : None if subm['posted_at'] is None else plm.parse(subm['posted_at']),
                   'late' : subm['late'],
                   'missing' : subm['missing'],
                   'excused' : subm['excused'],
            } for subm in subms ]

    logger = get_logger()
    logger.info(f"Retrieved {len(processed_subms)} submissions for assignment {assignment['name']} from LMS for {config.course_names[course_id]}")

    subms_map = {}
    for subm in processed_subms:
        if subm['assignment_id'] not in subms_map:
            subms_map[subm['assignment_id']] = {}
        subms_map[subm['assignment_id']][subm['student_id']] = subm
    return subms_map

def generate_update_override_name(config, course_id, override_update_tuple, **kwargs):
    return 'upd-override-'+ override_update_tuple[1]['title']

@task(checkpoint=False,task_run_name=generate_update_override_name)
def update_override(config, course_id, override_update_tuple):
    assignment, to_create, to_remove = override_update_tuple
    if to_remove is not None:
        _remove_override(config, course_id, assignment, to_remove)
    if to_create is not None:
        _create_override(config, course_id, assignment, to_create)


# TODO remove this function once https://github.com/PrefectHQ/prefect/issues/4084 is resolved
# and fix where this gets called in flows.py
def generate_update_override_flatten_name(config, course_id, override_update_tuples, **kwargs):
    return 'upd-override-flattened'

@task(checkpoint=False,task_run_name=generate_update_override_flatten_name)
def update_override_flatten(config, course_id, override_update_tuples):
    for override_update_tuple in override_update_tuples:
        assignment, to_create, to_remove = override_update_tuple
        if to_remove is not None:
            _remove_override(config, course_id, assignment, to_remove)
        if to_create is not None:
            _create_override(config, course_id, assignment, to_create)

def put_grade(config, course_id, student, assignment, score):
    # post the grade
    _canvas_put(config, course_id, 'assignments/'+assignment['id']+'/submissions/'+student['id'], {'submission' : {'posted_grade' : score}})

    # check that it was posted properly
    canvas_grade = str(_canvas_get(config, course_id, 'assignments/'+assignment['id']+'/submissions/'+student['id'])[0]['score'])
    if abs(float(score) - float(canvas_grade)) > 0.01:
        sig = signals.FAIL(f"grade {score} failed to upload for submission {subm['name']} ; grade on canvas is {canvas_grade}")
        sig.assignment = assignment
        sig.student = student
        sig.score = score
        sig.canvas_score = canvas_grade
        raise sig

# TODO add these in???
#def get_grades(course, assignment): #???
#    '''Takes a course object, an assignment name, and get the grades for that assignment from Canvas.
#
#    Example:
#    course.get_grades(course, 'worksheet_01')'''
#    assignment_id = get_assignment_id(course, assignment)
#    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", assignment_id, "submissions")
#    api_url = urllib.parse.urljoin(course['hostname'], url_path)
#    token = course['token']
#
#    resp = None
#    scores = {}
#    while resp is None or resp.links['current']['url'] != resp.links['last']['url']:
#        resp = requests.get(
#            url = api_url if resp is None else resp.links['next']['url'],
#            headers = {
#                "Authorization": f"Bearer {token}",
#                "Accept": "application/json+canvas-string-ids"
#                },
#            json={
#              "per_page":"100"
#            }
#        )
#        scores.update( {res['user_id'] : res['score'] for res in resp.json()} )
#    return scores
#


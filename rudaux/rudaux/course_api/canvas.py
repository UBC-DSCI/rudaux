import requests
import urllib.parse
import pendulum as plm
from prefect import task
from prefect.engine import signals

def _canvas_get(config, path_suffix, use_group_base=False):
    group_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/groups/')
    base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+config.canvas_id+'/')
    token = config.canvas_token

    if use_group_base:
        url = urllib.parse.urljoin(group_url, path_suffix)
    else:
        url = urllib.parse.urljoin(base_url, path_suffix)
    resp = None
    resp_items = []
    #see https://community.canvaslms.com/t5/Question-Forum/Why-is-the-Assignment-due-at-value-that-of-the-last-override/m-p/209593
    #for why we have to set override_assignment_dates = false below -- basically due_at below gets set really weirdly if
    #the assignment has overrides unless you include this param
    while resp is None or 'next' in resp.links.keys():
        resp = requests.get(
            url = url if resp is None else resp.links['next']['url'],
            headers = {
                'Authorization': f'Bearer {config.canvas_token}',
                'Accept': 'application/json'
                },
            json = {'per_page' : 100},
            params = {'override_assignment_dates' : False}
        )

        if resp.status_code < 200 or resp.status_code > 299:
            sig = signals.FAIL("failed GET response status code " + str(resp.status_code) + " for URL: " + str(url))
            sig.url = url
            sig.resp = resp            
            raise sig

        json_data = resp.json()
        if isinstance(json_data, list):
            resp_items.extend(resp.json())
        else:
            resp_items.append(resp.json())
    return resp_items

def _canvas_upload(config, path_suffix, json_data, typ):
    rfuncs = {'put' : requests.put,
             'post': requests.post,
             'delete': requests.delete}
    url = urllib.parse.urljoin(base_url, path_suffix)
    resp = rfuncs[typ](
        url = url,
        headers = {
            'Authorization': f'Bearer {config.canvas_token}',
            'Accept': 'application/json'
            },
        json=json_data
    )
    if resp.status_code < 200 or resp.status_code > 299:
        sig = signals.FAIL("failed upload (" + typ + ")  response status code " + str(resp.status_code) + " for URL: " + str(url))
        sig.url = url
        sig.resp = resp            
        raise sig
    return
     
def _canvas_put(config, path_suffix, json_data):
    _canvas_upload(config, path_suffix, json_data, 'put')

def _canvas_post(config, path_suffix, json_data):
    _canvas_upload(config, path_suffix, json_data, 'post')

def _canvas_delete(config, path_suffix):
    _canvas_upload(config, path_suffix, None, 'delete')

def _canvas_get_people_by_type(config, typ):
    people = _canvas_get(config, 'enrollments')
    ppl_typ = [p for p in people if p['type'] == typ]
    return [ { 'id' : str(p['user']['id']),
               'name' : p['user']['name'],
               'sortable_name' : p['user']['sortable_name'],
               'school_id' : str(p['user']['sis_user_id']),
               'reg_date' : plm.parse(p['updated_at']) if (plm.parse(p['updated_at']) is not None) else plm.parse(p['created_at']),
               'status' : p['enrollment_state']
              } for p in ppl_typ
           ] 

def _canvas_get_overrides(config, assignment):
    overs = _canvas_get(config, 'assignments/'+assignment['id']+'/overrides')
    for over in overs:
        over['id'] = str(over['id'])
        over['student_ids'] = list(map(str, over['student_ids']))
        for key in ['due_at', 'lock_at', 'unlock_at']:
            if over.get(key) is not None:
                over[key] = plm.parse(over[key])
            else:
                over[key] = None
    return overs

@task
def validate_config(config):
    #TODO validate these all strings, format, etc
    #config.canvas_domain
    #config.canvas_token 
    #config.canvas_id 
    return config

@task
def get_course_info(config):
    return _canvas_get(config,'')[0]

@task
def get_students(config):
    return _canvas_get_people_by_type(config,'StudentEnrollment')

@task
def get_instructors(config):
    return _canvas_get_people_by_type(config,'TeacherEnrollment')

@task
def get_tas(config):
    return _canvas_get_people_by_type(config,'TaEnrollment')

@task
def get_groups(config):
    grps = _canvas_get(config,'groups')
    return [{
             'name' : g['name'],
             'id' : str(g['id']),
             'members' : [str(m['user_id']) for m in _canvas_get(config, str(g['id'])+'/memberships', use_group_base=True)]
            } for g in grps]

@task
def get_assignments(config, grader_type_identifier):
    asgns = _canvas_get(config, 'assignments')
    processed_asgns = [ {  
               'id' : str(a['id']),
               'name' : a['name'],
               'due_at' : None if a['due_at'] is None else plm.parse(a['due_at']),
               'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at']),
               'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at']),
               'has_overrides' : a['has_overrides'],
               'overrides' : [],
               'published' : a['published'],
               'grader_type' : grader_type_identifier(a)
             } for a in asgns]
# TODO the below commented out code filters for jupyterhub assignments. need to put this code elsewhere
# if 'external_tool_tag_attributes' in a.keys() and self.jupyterhub_host_root in a['external_tool_tag_attributes']['url'] and a['omit_from_final_grade'] == False]
#config.jupyterhub_host_root # 
    for a in processed_asgns:
        if a['has_overrides']:
            a['overrides'] = _canvas_get_overrides(config, a)

    return processed_asgns

@task
def get_submissions(config, assignment):
    subms = _canvas_get(config, 'assignments/'+assignment['id']+'/submissions')
    return [ {
                   'student_id' : str(subm['user_id']), 
                   'assignment_id' : assignment['id'],
                   'score' : subm['score'],
                   'posted_at' : None if subm['posted_at'] is None else plm.parse(subm['posted_at']),
                   'late' : subm['late'],
                   'missing' : subm['missing']
            } for subm in subms ]

def create_override(config, assignment, override_dict):
    #check all required keys
    required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
    for rk in required_keys:
        if not override_dict.get(rk):
            sig = signals.FAIL("invalid override for assignment " + str(assignment['name']) +"("+str(assignment['id'])+"): dict missing required key " + rk)
            sig.assignment = assignment
            sig.override_dict = override_dict
            sig.missing_key = rk
            raise sig

    #convert student ids to integers
    override_dict['student_ids'] = list(map(int, override_dict['student_ids']))

    #convert dates to canvas date time strings in the course local timezone
    for dk in ['unlock_at', 'due_at', 'lock_at']:
        override_dict[dk] = str(override_dict[dk])

    #post the override
    post_json = {'assignment_override' : override_dict}
    _canvas_post(config, 'assignments/'+assignment['id']+'/overrides', post_json)

    #check that it posted properly 
    overs = _canvas_get_overrides(config, assignment)
    n_match = len([over for over in overs if over['title'] == override_dict['title']])
    if n_match != 1:
        sig = signals.FAIL("override for assignment " + str(assignment['name']) +"("+str(assignment['id'])+") failed to upload to Canvas")
        sig.assignment = assignment
        sig.attempted_override = override_dict
        sig.overrides = overs
        raise sig

def remove_override(config, assignment, override):
    _canvas_delete(config, 'assignments/'+assignment['id']+'/overrides/'+override['id'])

    #check that it was removed properly 
    overs = _canvas_get_overrides(config, assignment)
    n_match = len([over for over in overs if over['id'] == override['id']])
    if n_match != 0:
        sig = signals.FAIL("override " + str(override['title']) + " for assignment " + str(assignment['name']) + "("+str(assignment['id'])+") failed to be removed from Canvas")
        sig.override = override
        sig.assignment = assignment
        sig.overrides = overs
        raise sig

def put_grade(config, assignment, student, score):
    _canvas_put(config, 'assignments/'+assignment['id']+'/submissions/'+student['id'], {'submission' : {'posted_grade' : score}})

    #check that it was posted properly
    canvas_grade = str(_canvas_get(config, 'assignments/'+assignment['id']+'/submissions/'+student['id'])[0]['score'])
    if abs(float(score) - float(canvas_grade)) > 0.01:
        sig = signals.FAIL("grade (" + str(score) +") failed to upload for assignment " + str(assignment['name']) + "("+str(assignment['id'])+"), student " + str(student['name']) + "("+str(student['id'])+"); grade on canvas is " + str(canvas_grade))
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


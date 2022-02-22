import inspect
import requests
import urllib.parse
import pendulum as plm
import prefect
from prefect import task, Flow
from prefect.engine import signals
from .utilities import get_logger

# TODO replace "course api" with "LMS"

def _canvas_get(canvas_domain, canvas_token, course_id, path_suffix, use_group_base=False, verbose=False):
    """
    Request course information from Canvas.
        
    Parameters
    ----------
    config: traitlets.config.loader.Config
        a dictionary-like object, loaded from rudaux_config.py
    course_id: str
        the course id as string. 
    path_suffix: str
        specifies the component/item to be edit
    use_group_base: bool, default False
        
        
    Returns
    -------
        List of requested items.
    """
    group_url = urllib.parse.urljoin(canvas_domain, 'api/v1/groups/')
    base_url = urllib.parse.urljoin(canvas_domain, 'api/v1/courses/'+course_id+'/')

    if use_group_base:
        url = urllib.parse.urljoin(group_url, path_suffix)
    else:
        url = urllib.parse.urljoin(base_url, path_suffix)

    if verbose:
        print(f"GET request to URL: {url}")

    resp = None
    resp_items = []
    #see https://community.canvaslms.com/t5/Question-Forum/Why-is-the-Assignment-due-at-value-that-of-the-last-override/m-p/209593
    #for why we have to set override_assignment_dates = false below -- basically due_at below gets set really weirdly if
    #the assignment has overrides unless you include this param
    while resp is None or 'next' in resp.links.keys():
        resp = requests.get(
            url = url if resp is None else resp.links['next']['url'],
            headers = {
                'Authorization': f'Bearer {canvas_token}',
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


def _canvas_upload(config, course_id, path_suffix, json_data, type_request):
    """
    Base functions to create PUT/POST/DELETE requests to Canvas.
    
    Parameters
    ----------
    config: traitlets.config.loader.Config
        a dictionary-like object, loaded from rudaux_config.py
    course_id: str
        the course id as string. 
    path_suffix: str
        specifies the component/item to be edit
    json_data: dict
        the data to be uploaded if any. Use None for DELETE requests
    type_request: str
        the type of the request. Valid values are 'PUT', 'POST', or 'DELETE'. 
    """
   
    base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+course_id+'/')
    url = urllib.parse.urljoin(base_url, path_suffix)
    
    token = config.course_tokens[course_id]
    request_funcs = {'put' : requests.put,
                     'post': requests.post,
                     'delete': requests.delete}
    
    logger = get_logger()
    logger.info(f"{type_request.upper()} request to URL: {url}")

    resp = request_funcs[type_request.lower()](
        url = url,
        headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        },
        json=json_data
    )
    
    if resp.status_code < 200 or resp.status_code > 299:
        sig = signals.FAIL(f"Failed ({type_request.upper()}) request. Response status code {resp.status_code} for URL {url}\nText:{resp.text}")
        sig.url = url
        sig.resp = resp
        raise sig
    
    return


def _canvas_put(config, course_id, path_suffix, json_data):
    """
    Make a PUT request.
    
    Parameters
    ----------
    config: traitlets.config.loader.Config
        a dictionary-like object, loaded from rudaux_config.py
    course_id: str
        the course id as string. 
    path_suffix: str
        specifies the component/item to be edit
    json_data: dict
        the data to be uploaded
    """
    _canvas_upload(config, course_id, path_suffix, json_data, 'put')


def _canvas_post(config, course_id, path_suffix, json_data):
    """
    Make a POST request.
    
    Parameters
    ----------
    config: traitlets.config.loader.Config
        a dictionary-like object, loaded from rudaux_config.py
    course_id: str
        the course id as string. 
    path_suffix: str
        specifies the component/item to be edit
    json_data: dict
        the data to be uploaded if any
    """
    _canvas_upload(config, course_id, path_suffix, json_data, 'post')


def _canvas_delete(config, course_id, path_suffix):    
    """
    Make a DELETE request.
    
    Parameters
    ----------
    config: traitlets.config.loader.Config
        a dictionary-like object, loaded from rudaux_config.py
    course_id: str
        the course id as string. 
    path_suffix: str
        specifies the component/item to be edit
    """
    _canvas_upload(config, course_id, path_suffix, None, 'delete')


def _canvas_get_overrides(canvas_domain, canvas_token, course_id, assignment_id):
    overs = _canvas_get(canvas_domain, canvas_token, course_id, 'assignments/'+assignment_id+'/overrides')
    for over in overs:
        over['id'] = str(over['id'])
        over['student_ids'] = list(map(str, over['student_ids'])) if 'students' in over else []
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

class Course:

    def __init__(self, canvas_domain, canvas_token, course_id):
        self.domain = canvas_domain
        self.token = canvas_token
        self.id = course_id
        self._get_course_info()

    @property
    def people(self):
        return self.__people

    @property
    def students(self):
        return [p for p in self.people if p['type'] == 'StudentEnrollment']
    
    @property
    def teaching_assistants(self):
        return [p for p in self.people if p['type'] == 'TaEnrollment']
    
    @property
    def instructors(self):
        return [p for p in self.people if p['type'] == 'TeacherEnrollment']

    @property
    def groups(self):
        return self.__groups

    @property
    def assignments(self):
        return [{key: a[key] for key in a.keys() if key != 'overrides'} for a in self.__assignments]

    @property
    def overrides(self):
        return self.__assignments

    def overrides_by_assignment(self, assignment_id):
        return list(filter(lambda x: x['id'] == assignment_id, self.overrides))[0]['overrides']

    def _get_course_info(self):
        info = _canvas_get(self.domain, self.token, self.id, '')[0]
        self.name = info['name']
        self.code = info['course_code']
        self.start_at = None if info['start_at'] is None else plm.parse(info['start_at'])
        self.end_at = None if info['end_at'] is None else plm.parse(info['end_at'])
        self.time_zone = info['time_zone']

    def get_people(self, force=False, verbose=False):
        """
        Get all people involved in the couse (e.g., instructors, TAs, students)

        Parameters
        ----------
        force: bool
            Forces the request and overwrites `people` attribute.
        """
        if not force and "people" in self.__dict__.keys():
            raise AttributeError("People has already been fetched. Use force=True to overwrite it.")

        if verbose:
            print("Fetching course enrollments.", end='')

        people = _canvas_get(self.domain, self.token, self.id, 'enrollments')
        self.__people = [ { 'id': str(p['user']['id']),
                'name': p['user']['name'],
                'sortable_name': p['user']['sortable_name'],
                'school_id': str(p['user']['sis_user_id']),
                'reg_date': plm.parse(p['updated_at']) if (plm.parse(p['updated_at']) is not None) else plm.parse(p['created_at']),
                'status': p['enrollment_state'],
                'type': p['type']
                } for p in people ]
        if verbose:
            print("Done!")
        
    def get_groups(self, verbose=False):
        
        if verbose:
            print("Getting the list of existing groups. ", end='')
        grps = _canvas_get(self.domain, self.token, self.id, 'groups')
        
        if verbose:
            print("Done!")
            print(f"Retrieved {len(grps)} groups from Canvas for {self.name}")
            print(f"Retrieving group members. ", end='')

        self.__groups = [{
                'name': g['name'],
                'id': str(g['id']),
                'members': [str(m['user_id']) for m in _canvas_get(self.domain, self.token, self.id, str(g['id'])+'/memberships', use_group_base=True)]
                } for g in grps]
        
        if verbose:
            print("Done!")
    
    def get_assignments(self, verbose=False):

        if verbose:
            print("Fetching course's assignments: ", end='')
        
        asgns = _canvas_get(self.domain, self.token, self.id, 'assignments')
        
        if verbose:
            print("Done!")
            print(f"Retrieved {len(asgns)} assignments from Canvas for {self.name}")
            print("Processing assignments: ", end='')
        
        self.__assignments = [ {
                'id' : str(a['id']),
                'name' : a['name'],
                'due_at' : None if a['due_at'] is None else plm.parse(a['due_at']),
                'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at']),
                'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at']),
                'has_overrides' : a['has_overrides'],
                'overrides' : [],
                'published' : a['published']
                } for a in asgns]
        
        if verbose:
            print("Done!")
            print("Fetching overrides: ", end='')
        
        # fill out overrides
        for a in self.__assignments:
            if a['has_overrides']:
                a['overrides'] = _canvas_get_overrides(self.domain, self.token, self.id, a['id'])

        if verbose:
            print("Done!")

        # check for duplicate IDs and names
        # we require both of these to be unique (snapshots, grader accounts, etc all depend on unique human-readable names)
        ids = [a['id'] for a in self.__assignments]
        names = [a['name'] for a in self.__assignments]
        if len(set(ids)) != len(ids):
            sig = signals.FAIL(f"Course ID {self.id}: Two assignments detected with the same ID. IDs: {ids}")
            sig.course_id = self.id
            raise sig
        if len(set(names)) != len(names):
            sig = signals.FAIL(f"Course ID {self.id}: Two assignments detected with the same name. Names: {names}")
            sig.course_id = self.id
            raise sig

    def get_submissions(self, assignment_id, verbose=False):
        subms = _canvas_get(self.domain, self.token, self.id, 'assignments/'+assignment_id+'/submissions')
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

    def __str__(self):
        course_info = f"Course: {self.name}\n" +\
                      f"Code: {self.code}\n" +\
                      f"Id: {self.id}\n" +\
                      f"Start at: {self.start_at}\n" +\
                      f"End at: {self.end_at}\n" +\
                      f"Assignments: {self.__dict__.get('assignments') if self.__dict__.get('assignments') else 'not fetched'}\n"

        return course_info

    def __repr__(self):
        return f"Course({self.domain}, {self.token}, {self.id})"
        


@task(checkpoint=False)
def generate_get_submissions_name(config, course_id, assignment, **kwargs):
    return 'get-subms-'+assignment['name']

@task(checkpoint=False, task_run_name=generate_get_submissions_name)
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
def generate_update_override_flatten_name(config, course_id, override_update_tuple, **kwargs):
    return 'upd-override-'+ override_update_tuple[1]['title']

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


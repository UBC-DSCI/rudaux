import requests
import urllib.parse
import pendulum as plm
from functools import lru_cache

class CanvasGetError(Exception):
    def __init__(self, url, resp):
        self.url = url
        self.resp = resp

class CanvasUploadError(Exception):
    def __init__(self, url, resp, typ):
        self.typ = typ
        self.url = url
        self.resp = resp

class InvalidOverrideError(Exception):
    def __init__(self, override_dict, missing_key=None, multiple_students=False):
        self.override_dict = override_dict
        self.missing_key = missing_key
        self.multiple_students = multiple_students

class OverrideUploadError(Exception):
    def __init__(self, overrides, override_to_upload):
        self.overrides = overrides
        self.override_to_upload = override_to_upload

class OverrideRemoveError(Exception):
    def __init__(self, overrides, override_id):
        self.overrides = overrides
        self.override_id = override_id

class Canvas(object):
    """
    Interface to the Canvas REST API
    """

    def __init__(self, config, dry_run):
        self.base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+config.canvas_id+'/')
        self.token = config.canvas_token
        self.jupyterhub_host_root = config.jupyterhub_host_root
        self.dry_run = dry_run

    #cache subsequent calls to avoid slow repeated access to canvas api
    @lru_cache(maxsize=None)
    def get(self, path_suffix):
        url = urllib.parse.urljoin(self.base_url, path_suffix)
        resp = None
        resp_items = []
        while resp is None or 'next' in resp.links.keys():
            resp = requests.get(
                url = url if resp is None else resp.links['next']['url'],
                headers = {
                    'Authorization': f'Bearer {self.token}',
                    'Accept': 'application/json'
                    },
                json = {
                    'per_page' : 100
                }
            )

            if resp.status_code < 200 or resp.status_code > 299:
                raise CanvasGetError(url, resp)

            json_data = resp.json()
            if isinstance(json_data, list):
                resp_items.extend(resp.json())
            else:
                resp_items.append(resp.json())

        return resp_items

    def upload(self, path_suffix, json_data, typ):
        rfuncs = {'put' : requests.put,
                 'post': requests.post,
                 'delete': requests.delete}
        url = urllib.parse.urljoin(self.base_url, path_suffix)
        if not self.dry_run:
            resp = rfuncs[typ](
                url = url,
                headers = {
                    'Authorization': f'Bearer {self.token}',
                    'Accept': 'application/json'
                    },
                json=json_data
            )
            if resp.status_code < 200 or resp.status_code > 299:
                raise CanvasUploadError(url, resp, typ)
        else:
            print('[Dry Run: would have made a ' + typ + ' request with URL: ' + url + ']')
        return
         

    def put(self, path_suffix, json_data):
        self.upload(path_suffix, json_data, 'put')

    def post(self, path_suffix, json_data):
        self.upload(path_suffix, json_data, 'post')

    def delete(self, path_suffix, json_data):
        self.upload(path_suffix, json_data, 'delete')

    def get_course_info(self):
        return self.get('')[0]

    def _get_people_by_type(self, typ):
        people = self.get('enrollments')
        ppl_typ = [p for p in people if p['type'] == typ]
        tz = self.get_course_info()['time_zone']
        return [ { 'name' : p['user']['name'],
                   'sortable_name' : p['user']['sortable_name'],
                   'short_name' : p['user']['short_name'],
                   'canvas_id' : str(p['user']['id']),
                   'sis_id' : str(p['user']['sis_user_id']),
                   'reg_created' : plm.parse(p['created_at'], tz=tz),
                   'reg_updated' : plm.parse(p['updated_at'], tz=tz),
                   'status' : p['enrollment_state']
                  } for p in ppl_typ
               ] 

    def get_students(self):
        return self._get_people_by_type('StudentEnrollment')
  
    def get_fake_students(self):
        return self._get_people_by_type('StudentViewEnrollment')
        
    def get_instructors(self):
        return self._get_people_by_type('TeacherEnrollment')

    def get_tas(self):
        return self._get_people_by_type('TaEnrollment')

    def get_assignments(self):
        asgns = self.get('assignments')
        tz = self.get_course_info()['time_zone']
        processed_asgns = [ {  
                   'canvas_id' : str(a['id']),
                   'name' : a['name'],
                   'due_at' : None if a['due_at'] is None else plm.parse(a['due_at'], tz=tz),
                   'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at'], tz=tz),
                   'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at'], tz=tz),
                   'points_possible' : a['points_possible'],
                   'grading_type' : a['grading_type'],
                   'workflow_state' : a['workflow_state'],
                   'has_overrides' : a['has_overrides'],
                   'overrides' : [],
                   'published' : a['published']
                 } for a in asgns if 'external_tool_tag_attributes' in a.keys() and self.jupyterhub_host_root in a['external_tool_tag_attributes']['url'] ]
        for a in processed_asgns:
            if a['has_overrides']:
                a['overrides'] = self.get_overrides(a['canvas_id'])

        return processed_asgns

    def get_submissions(self, assignment_id):
        tz = self.get_course_info()['time_zone']
        subms = self.get('assignments/'+assignment_id+'/submissions')
        return [ {
                       'student_id' : str(subm['user_id']), 
                       'assignment_id' : assignment_id,
                       'grade' : subm['grade'],
                       'score' : subm['score'],
                       'workflow_state' : subm['workflow_state'],
                       'excused' : subm['excused'],
                       'late_policy_status' : subm['late_policy_status'],
                       'points_deducted' : subm['points_deducted'],
                       'posted_at' : None if subm['posted_at'] is None else plm.parse(subm['posted_at'], tz=tz),
                       'late' : subm['late'],
                       'missing' : subm['missing'],
                       'entered_grade' : subm['entered_grade'],
                       'entered_score' : subm['entered_score']
                } for s in subms ]

    def get_overrides(self, assignment_id):
        tz = self.get_course_info()['time_zone']
        overs = self.get('assignments/'+assignment_id+'/overrides')
        print(overs)
        for over in overs:
            print(over)
            over['id'] = str(over['id'])
            over['student_ids'] = list(map(str, over['student_ids']))
            for key in ['due_at', 'lock_at', 'unlock_at']:
                if over.get(key) is not None:
                    over[key] = plm.parse(over[key], tz=tz)
                else:
                    over[key] = None
        return overs

    def create_override(self, assignment_id, override_dict):
        tz = self.get_course_info()['time_zone']
        #check all required keys
        required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
        for rk in required_keys:
            if not override_dict.get(rk):
                raise InvalidOverrideError(override_dict, missing_key=rk)

        #convert student ids to integers
        override_dict['student_ids'] = list(map(int, override_dict['student_ids']))

        #convert dates to canvas date time strings in the course local timezone
        for dk in ['unlock_at', 'due_at', 'lock_at']:
            override_dict[dk] = override_dict[dk].in_timezone(tz).format('YYYY-MM-DDTHH:mm:ss\Z')

        #post the override
        post_json = {'assignment_override' : override_dict}
        self.post('assignments/'+assignment_id+'/overrides', post_json)

        #check that it posted properly (only if not dry run)
        if not self.dry_run:
            overs = self.get_overrides(assignment_id)
            n_match = len([over for over in overs if over['title'] == override_dict['title']])
            if n_match != 1:
                raise OverrideUploadError(overs, override_dict)    

    def remove_override(self, assignment_id, override_id):
        self.delete('assignments/'+assignment_id+'/overrides/'+override_id)

        #check that it was removed properly (only if not a dry run)
        if not self.dry_run:
            overs = self.get_overrides(assignment_id)
            n_match = len([over for over in overs if over['id'] == override_id])
            if n_match != 0:
                raise OverrideRemoveError(overs, override_id)    

    def put_grade(self, assignment_id, student_id, score):
        self.put('assignments/'+assignment_id+'/submissions/'+student_id, {'posted_grade' : score})
        
        #check that it was posted properly
        #TODO
        

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
#def grades_need_posting(course, assignment):
#    '''Takes a course object, an assignment name, and get the grades for that assignment from Canvas.
#    
#    Example:
#    course.get_grades(course, 'worksheet_01')'''
#    assignment_id = get_assignment_id(course, assignment)
#    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", assignment_id, "submissions")
#    api_url = urllib.parse.urljoin(course['hostname'], url_path)
#    token = course['token']
#
#    #get enrollments to avoid the test student's submissions
#    real_stu_ids = list(get_enrollment_dates(course).keys())
#  
#    resp = None
#    posted_flags = []
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
#        posted_flags.extend([ (subm_grd['posted_at'] is not None) for subm_grd in resp.json() if subm_grd['user_id'] in real_stu_ids])
#
#    return not all(posted_flags)



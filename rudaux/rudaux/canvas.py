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

class GradeNotUploadedError(Exception):
    def __init__(self, uploaded_val, actual_val):
        self.message = 'Grade on canvas not equal to the uploaded grade. Uploaded grade: ' + str(uploaded_val) + ' Canvas grade: ' + str(actual_val)
    

class Canvas(object):
    """
    Interface to the Canvas REST API
    """

    def __init__(self, config):
        self.group_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/groups/')
        self.base_url = urllib.parse.urljoin(config.canvas_domain, 'api/v1/courses/'+config.canvas_id+'/')
        self.token = config.canvas_token
        self.jupyterhub_host_root = config.jupyterhub_host_root

    #cache subsequent calls to avoid slow repeated access to canvas api
    #@lru_cache(maxsize=None) TODO -- be careful, e.g., get_overrides overwrites the dict return, which is cached
    #so when you call get again it breaks things
    #disabling the cache for now. In the future should call cache_clear() when certain get functions are called.
    #also sometimes we need to force no cache when synchronizing (after various updates)
    def get(self, path_suffix, use_group_base=False):
        if use_group_base:
            url = urllib.parse.urljoin(self.group_url, path_suffix)
        else:
            url = urllib.parse.urljoin(self.base_url, path_suffix)
        resp = None
        resp_items = []
        #see https://community.canvaslms.com/t5/Question-Forum/Why-is-the-Assignment-due-at-value-that-of-the-last-override/m-p/209593
        #for why we have to set override_assignment_dates = false below -- basically due_at below gets set really weirdly if
        #the assignment has overrides unless you include this param
        while resp is None or 'next' in resp.links.keys():
            resp = requests.get(
                url = url if resp is None else resp.links['next']['url'],
                headers = {
                    'Authorization': f'Bearer {self.token}',
                    'Accept': 'application/json'
                    },
                json = {'per_page' : 100},
                params = {'override_assignment_dates' : False}
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
        resp = rfuncs[typ](
            url = url,
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/json'
                },
            json=json_data
        )
        if resp.status_code < 200 or resp.status_code > 299:
            print('Canvas Upload Error: ' + str(resp.reason))
            raise CanvasUploadError(url, resp, typ)
        return
         

    def put(self, path_suffix, json_data):
        self.upload(path_suffix, json_data, 'put')

    def post(self, path_suffix, json_data):
        self.upload(path_suffix, json_data, 'post')

    def delete(self, path_suffix):
        self.upload(path_suffix, None, 'delete')

    def get_course_info(self):
        return self.get('')[0]

    def _get_people_by_type(self, typ):
        people = self.get('enrollments')
        ppl_typ = [p for p in people if p['type'] == typ]
        return [ { 'name' : p['user']['name'],
                   'sortable_name' : p['user']['sortable_name'],
                   'short_name' : p['user']['short_name'],
                   'canvas_id' : str(p['user']['id']),
                   'sis_id' : str(p['user']['sis_user_id']),
                   'reg_created' : plm.parse(p['created_at']),
                   'reg_updated' : plm.parse(p['updated_at']),
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

    def get_groups(self):
        grps = self.get('groups')
        return [{
                 'name' : g['name'],
                 'canvas_id' : str(g['id']),
                 'members' : [str(m['user_id']) for m in self.get(str(g['id'])+'/memberships', use_group_base=True)]
                } for g in grps]


    def get_assignments(self):
        asgns = self.get('assignments')
        processed_asgns = [ {  
                   'canvas_id' : str(a['id']),
                   'name' : a['name'],
                   'due_at' : None if a['due_at'] is None else plm.parse(a['due_at']),
                   'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at']),
                   'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at']),
                   'points_possible' : a['points_possible'],
                   'grading_type' : a['grading_type'],
                   'workflow_state' : a['workflow_state'],
                   'has_overrides' : a['has_overrides'],
                   'overrides' : [],
                   'published' : a['published']
                 } for a in asgns if 'external_tool_tag_attributes' in a.keys() and self.jupyterhub_host_root in a['external_tool_tag_attributes']['url'] and a['omit_from_final_grade'] == False]
        for a in processed_asgns:
            if a['has_overrides']:
                a['overrides'] = self.get_overrides(a['canvas_id'])

        return processed_asgns

    def get_submissions(self, assignment_id):
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
                       'posted_at' : None if subm['posted_at'] is None else plm.parse(subm['posted_at']),
                       'late' : subm['late'],
                       'missing' : subm['missing'],
                       'entered_grade' : subm['entered_grade'],
                       'entered_score' : subm['entered_score']
                } for subm in subms ]

    def get_overrides(self, assignment_id):
        overs = self.get('assignments/'+assignment_id+'/overrides')
        for over in overs:
            over['id'] = str(over['id'])
            over['student_ids'] = list(map(str, over['student_ids']))
            for key in ['due_at', 'lock_at', 'unlock_at']:
                if over.get(key) is not None:
                    over[key] = plm.parse(over[key])
                else:
                    over[key] = None
        return overs

    def create_override(self, assignment_id, override_dict):
        #check all required keys
        required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
        for rk in required_keys:
            if not override_dict.get(rk):
                raise InvalidOverrideError(override_dict, missing_key=rk)

        #convert student ids to integers
        override_dict['student_ids'] = list(map(int, override_dict['student_ids']))

        #convert dates to canvas date time strings in the course local timezone
        for dk in ['unlock_at', 'due_at', 'lock_at']:
            override_dict[dk] = str(override_dict[dk])

        #post the override
        post_json = {'assignment_override' : override_dict}
        self.post('assignments/'+assignment_id+'/overrides', post_json)

        #check that it posted properly 
        overs = self.get_overrides(assignment_id)
        n_match = len([over for over in overs if over['title'] == override_dict['title']])
        if n_match != 1:
            raise OverrideUploadError(overs, override_dict)    

    def remove_override(self, assignment_id, override_id):
        self.delete('assignments/'+assignment_id+'/overrides/'+override_id)

        #check that it was removed properly
        overs = self.get_overrides(assignment_id)
        n_match = len([over for over in overs if over['id'] == override_id])
        if n_match != 0:
            raise OverrideRemoveError(overs, override_id)    

    def put_grade(self, assignment_id, student_id, score):
        self.put('assignments/'+assignment_id+'/submissions/'+student_id, {'submission' : {'posted_grade' : score}})
        #check that it was posted properly
        #TODO make this less awful code
        canvas_grade = str(self.get('assignments/'+assignment_id+'/submissions/'+student_id)[0]['score'])
        if abs(float(score) - float(canvas_grade)) > 0.01:
            raise GradeNotUploadedError(score, canvas_grade)

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


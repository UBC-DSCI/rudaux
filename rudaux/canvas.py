import requests
import urllib.parse
import pendulum as plm
from functools import lru_cache

class Canvas(object):
    """
    Interface to the Canvas REST API
    """

    def __init__(self, course):
        self.base_url = urllib.parse.urljoin(course.config.canvas_domain, 'api/v1/courses/'+course.config.canvas_id+'/')
        self.token = course.config.canvas_token
        self.jupyterhub_host_roots = course.config.jupyterhub_host_roots

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
            json_data = resp.json()
            if isinstance(json_data, list):
                resp_items.extend(resp.json())
            else:
                resp_items.append(resp.json())
        if len(resp_items) == 1:
            return resp_items[0]
        return resp_items

    def put(self, path_suffix, json_data):
        url = urllib.parse.urljoin(self.base_url, path_suffix)
        resp = requests.put(
            url = url,
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/json'
                },
            json=json_data
        )

    def get_course_info(self):
        return self.get('')

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
        
    def get_teachers(self):
        return self._get_people_by_type('TeacherEnrollment')

    def get_tas(self):
        return self._get_people_by_type('TaEnrollment')

    def get_assignments(self):
        asgns = self.get('assignments')
        tz = self.get_course_info()['time_zone']
        return [ {  'id' : str(a['id']),
                   'name' : a['name'],
                   'due_at' : None if a['due_at'] is None else plm.parse(a['due_at'], tz=tz),
                   'lock_at' : None if a['lock_at'] is None else plm.parse(a['lock_at'], tz=tz),
                   'unlock_at' : None if a['unlock_at'] is None else plm.parse(a['unlock_at'], tz=tz),
                   'points_possible' : a['points_possible'],
                   'grading_type' : a['grading_type'],
                   'workflow_state' : a['workflow_state'],
                   'has_overrides' : a['has_overrides'],
                   'published' : a['published'],
                   'is_jupyterhub_assignment' : True if 'external_tool_tag_attributes' in a.keys() and len([hostroot for hostroot in self.jupyterhub_host_roots if hostroot in a['external_tool_tag_attributes']['url']]) > 0 else False,
                   'jupyterhub_host_root' : [hostroot for hostroot in self.jupyterhub_host_roots if hostroot in a['external_tool_tag_attributes']['url']][0] if 'external_tool_tag_attributes' in a.keys() and len([hostroot for hostroot in self.jupyterhub_host_roots if hostroot in a['external_tool_tag_attributes']['url']]) > 0 else None
                 } for a in asgns 
               ]
         
    def get_submissions(self, assignment):
        #todo get assignment id
        return self.get('assignments/'+assignment_id+'/submissions')

    def put_grades(self):
        pass
        
#def post_grade(course, assignment, student, score):
#    '''Takes a course object, an assignment name, student id, and score to upload. Posts to Canvas.
#
#    Example:
#    course.post_grades(dsci100, 'worksheet_01', '23423', 10)'''
#    assignment_id = get_assignment_id(course, assignment)
#    url_post_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", assignment_id, "submissions", student)
#    api_url = urllib.parse.urljoin(course['hostname'], url_post_path)
#    token = course['token']
#    resp = requests.put(
#        url = urllib.parse.urljoin(api_url, student),
#        headers = {
#            "Authorization": f"Bearer {token}",
#            "Accept": "application/json+canvas-string-ids"
#            },
#        json={
#            "submission": {"posted_grade": score}
#            },
#    )
#
#        
#
#def get_enrollment_dates(course):
#    '''Takes a course object and returns student dates of enrollment.
#    Useful for handling late registrations and modified deadlines.
#
#    Example:
#    course.get_enrollment_date()'''
#    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "enrollments")
#    api_url = urllib.parse.urljoin(course['hostname'], url_path)
#    token = course['token']
#    resp = None
#    students = []
#    while resp is None or resp.links['current']['url'] != resp.links['last']['url']:
#      #if first time or not done getting to all pages
#      resp = requests.get(
#          url = api_url if resp is None else resp.links['next']['url'],
#          headers = {
#              "Authorization": f"Bearer {token}",
#              "Accept": "application/json+canvas-string-ids"
#              },
#          json={
#            "type": ["StudentEnrollment"],
#            "per_page":"100" #try 5, find out the limit.
#          }
#      )
#      students.extend(resp.json())
#
#    enrollment_dates = {}
#    for st in students:
#      enrollment_dates[str(st['user_id'])] = str(st['created_at']).strip('Z').replace('T','-').replace(':','-')[:16]
#    return enrollment_dates
#
#def get_assignments(course):
#    '''Takes a course object and returns
#    a Pandas data frame with all existing assignments and their attributes/data
#
#    Example:
#    course.get_assignments()'''
#    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments")
#    api_url = urllib.parse.urljoin(course['hostname'], url_path)
#    token = course['token']
#    resp = requests.get(
#      url=api_url,
#      headers={
#        "Authorization": f"Bearer {token}",
#        "Accept": "application/json+canvas-string-ids"
#      },
#      json={
#        "per_page": "10000"
#      },
#    )
#    assignments = resp.json()
#    assign_data = pd.DataFrame.from_dict(assignments)
#    return assign_data
#
#def get_assignment_lock_date(course, assignment):
#    '''Takes a course object and the name of a Canvas assignment and returns the due date. Returns None if no due date assigned.
#    
#    Example:
#    course.get_assignment_due_date('worksheet_01')'''
#    assignments = get_assignments(course)
#    assignments = assignments[['name', 'lock_at']].query('name == @assignment')
#    lock_date = assignments['lock_at'].to_numpy()[0]
#    if lock_date is None:
#      return lock_date
#    lock_date = lock_date.replace("T", "-")
#    lock_date = lock_date.replace(":", "-")
#    return lock_date[:16]
#
#
#
#def get_assignment_due_date(course, assignment):
#    '''Takes a course object and the name of a Canvas assignment and returns the due date. Returns None if no due date assigned.
#    
#    Example:
#    course.get_assignment_due_date('worksheet_01')'''
#    assignments = get_assignments(course)
#    assignments = assignments[['name', 'due_at']].query('name == @assignment')
#    due_date = assignments['due_at'].to_numpy()[0]
#    if due_date is None:
#      return due_date
#    due_date = due_date.replace("T", "-")
#    due_date = due_date.replace(":", "-")
#    return due_date[:16]
#
#def get_assignment_unlock_date(course, assignment):
#    '''Takes a course object and the name of a Canvas assignment and returns the due date. Returns None if no due date assigned.
#    
#    Example:
#    course.get_assignment_unlock_date('worksheet_01')'''
#    assignments = get_assignments(course)
#    assignments = assignments[['name', 'unlock_at']].query('name == @assignment')
#    unlock_date = assignments['unlock_at'].to_numpy()[0]
#    if unlock_date is None:
#      return unlock_date
#    unlock_date = unlock_date.replace("T", "-").replace(':', '-')
#    return unlock_date[:16]
#
#
#def get_assignment_id(course, assignment):
#    '''Takes a course object and the name of a Canvas assignment and returns the Canvas ID.
#    
#    Example:
#    course.get_assignment_id('worksheet_01')'''
#    assignments = get_assignments(course)
#    assignments = assignments[['name', 'id']].query('name == @assignment')
#    return assignments['id'].values[0]
#
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



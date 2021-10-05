import requests
import urllib.parse
import pendulum as plm
from .utilities import get_logger

class Canvas:

    def __init__(self, info):
        self.info = info

    ########################
    # Public API functions
    ########################

    def get_course_info(self, course_name):
        course_info = self._get(course_name, '')[0]
        processed_info = {
                 "id" : str(course_info['id']),
                 "name" : course_info['name'],
                 "code" : course_info['course_code'],
                 "start_at" : None if course_info['start_at'] is None else plm.parse(course_info['start_at']),
                 "end_at" : None if course_info['end_at'] is None else plm.parse(course_info['end_at']),
                 "time_zone" : course_info['time_zone']
        }
        logger = get_logger()
        logger.info(f"Retrieved course info for {course_name}")
        return processed_info

    def get_people(self, course_name, enrollment_type):
        people = self._get(course_name, 'enrollments')
        ppl_typ = [p for p in people if p['type'] == enrollment_type]
        ppl = [ { 'id' : str(p['user']['id']),
                   'name' : p['user']['name'],
                   'sortable_name' : p['user']['sortable_name'],
                   'school_id' : str(p['user']['sis_user_id']),
                   'reg_date' : plm.parse(p['updated_at']) if (plm.parse(p['updated_at']) is not None) else plm.parse(p['created_at']),
                   'status' : p['enrollment_state']
                  } for p in ppl_typ
               ]
        logger = get_logger()
        logger.info(f"Retrieved {len(ppl)} students from LMS for {course_name}")
        return ppl

    def get_groups(self, course_name):
        grps = self._get(course_name,'groups')
        logger = get_logger()
        logger.info(f"Retrieved {len(grps)} groups from LMS for {course_name}")
        return [{
                 'name' : g['name'],
                 'id' : str(g['id']),
                 'members' : [str(m['user_id']) for m in self._get(course_name, str(g['id'])+'/memberships', use_group_base=True)]
                } for g in grps]

    def get_assignments(self, course_name):
        asgns = self._get(course_name, 'assignments')
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
                a['overrides'] = self.self._get_overrides(course_name, a)

        logger = get_logger()
        logger.info(f"Retrieved {len(processed_asgns)} assignments from LMS for {config.course_names[course_id]}")
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
            raise ValueError(f"Assignments from config missing in the course LMS.\nConfig: {assignment_names}\nLMS: {names}")

        return processed_asgns

    def get_submissions(self, course_name, assignment):
        subms = self._get(course_name, 'assignments/'+assignment['id']+'/submissions')
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
        logger.info(f"Retrieved {len(processed_subms)} submissions for assignment {assignment['name']} from LMS for {course_name}")

        subms_map = {}
        for subm in processed_subms:
            if subm['assignment_id'] not in subms_map:
                subms_map[subm['assignment_id']] = {}
            subms_map[subm['assignment_id']][subm['student_id']] = subm
        return subms_map

    def update_grade(self, course_name, submission):
        # post the grade
        self._put(course_name, 'assignments/'+assignment['id']+'/submissions/'+student['id'], {'submission' : {'posted_grade' : score}})

        # check that it was posted properly
        canvas_grade = str(self._get(config, course_id, 'assignments/'+assignment['id']+'/submissions/'+student['id'])[0]['score'])
        if abs(float(score) - float(canvas_grade)) > 0.01:
            raise ValueError(f"grade {score} failed to upload for submission {subm['name']} ; grade on canvas is {canvas_grade}")

    def update_extension(self, course_name, student, assignment, due_at):
        # find overrides for which student is already a member
        student_overs = []
        for override in assignment['overrides']:
            if student['id'] in override['student_ids']:
                student_overs.append(override)

        # remove from canvas all overrides involving that student
        # and remove the student from the list of ids in each override
        for override in student_overs:
            self._remove_override(course_name, assignment, override)
            override['student_ids'] = filter(lambda x : x != student['id'], override['student_ids'])

        # add a new override for just this student
        student_overs.append({'student_ids' : [student['id']],
                                    'title' : student['name'] + ' ' + assignment['name'],
                                    'unlock_at' : assignment['unlock_at'],
                                    'lock_at' : assignment['lock_at'],
                                    'due_at' : due_at})

        # reupload all the overrides + new one
        for override in student_overs:
            self._create_override(course_name, assignment, override)

    #################################
    # Basic Canvas HTTP API functions
    #################################

    def _get(self, course_name, path_suffix, use_group_base=False):
        canvas_domain = self.info[course_name]['domain']
        course_id = self.info[course_name]['id']
        token = self.info[course_name]['token']

        group_url = urllib.parse.urljoin(canvas_domain, 'api/v1/groups/')
        base_url = urllib.parse.urljoin(canvas_domain, 'api/v1/courses/'+course_id+'/')
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

            # raise any HTTP errors
            resp.raise_for_status()

            json_data = resp.json()
            if isinstance(json_data, list):
                resp_items.extend(resp.json())
            else:
                resp_items.append(resp.json())
        return resp_items

    def _upload(self, course_name, path_suffix, json_data, typ):
        canvas_domain = self.info[course_name]['domain']
        course_id = self.info[course_name]['id']
        token = self.info[course_name]['token']

        base_url = urllib.parse.urljoin(canvas_domain, 'api/v1/courses/'+course_id+'/')
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

        # raise any HTTP errors
        resp.raise_for_status()
        return

    def _put(self, course_name, path_suffix, json_data):
        self._upload(course_name, path_suffix, json_data, 'put')

    def _post(self, course_name, path_suffix, json_data):
        self._upload(course_name, path_suffix, json_data, 'post')

    def _delete(self, course_name, path_suffix):
        self._upload(course_name, path_suffix, None, 'delete')

    def _get_overrides(self, course_name, assignment):
        overs = self._get(course_name, 'assignments/'+assignment['id']+'/overrides')
        for over in overs:
            over['id'] = str(over['id'])
            over['title'] = str(over['title'])
            over['student_ids'] = list(map(str, over['student_ids']))
            for key in ['due_at', 'lock_at', 'unlock_at']:
                if over.get(key) is not None:
                    over[key] = plm.parse(over[key])
                else:
                    over[key] = None
        return overs

    def _create_override(course_name, assignment, override):
        #check all required keys
        required_keys = ['student_ids', 'unlock_at', 'due_at', 'lock_at', 'title']
        for rk in required_keys:
            if not override.get(rk):
                raise ValueError(f"invalid override for assignment {assignment['name']} ({assignment['id']}): dict missing required key {rk}")

        #convert student ids to integers
        override['student_ids'] = list(map(int, override['student_ids']))

        #convert dates to canvas date time strings in the course local timezone
        for dk in ['unlock_at', 'due_at', 'lock_at']:
            override[dk] = str(override[dk])

        #post the override
        post_json = {'assignment_override' : override}
        self._post(course_name, 'assignments/'+assignment['id']+'/overrides', post_json)

        #check that it posted properly
        overs = self._get_overrides(course_name, assignment)
        n_match = len([over for over in overs if over['title'] == override['title']])
        if n_match == 0:
            raise ValueError(f"override for assignment {assignment['name']} ({assignment['id'])}) failed to upload to Canvas")
        if n_match > 1:
            raise ValueError(f"multiple overrides for assignment {assignment['name']} ({assignment['id'])}) with title {override['title']} uploaded to Canvas")

    def _remove_override(course_name, assignment, override):
        self._delete(course_name, 'assignments/'+assignment['id']+'/overrides/'+override['id'])

        #check that it was removed properly
        overs = self._get_overrides(course_name, assignment)
        n_match = len([over for over in overs if over['id'] == override['id']])
        if n_match != 0:
            raise ValueError(f"override {override['title']} for assignment {assignment['name']} ({assignment['id']}) failed to be removed from Canvas")



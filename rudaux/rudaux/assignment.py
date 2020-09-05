from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool
import datetime
import shutil
import docker


class Assignment:
    # Class Attributes ?
        #TODO
        #shared path goes here
    
    # Instance Attributes
    #TODO add grader
    def __init__(self):
        self.assignment_info = {}
        ''' info contains the following entries:
            {'id': 15220351, #id
            'description': '',
            'due_at': '2020-10-01T05:59:59Z', #due date
            'unlock_at': '2020-05-12T06:00:00Z', #unlock date
            'lock_at': '2020-11-29T06:59:59Z', #lock date
            'points_possible': 35.0,
            'grading_type': 'points',
            'assignment_group_id': 2876358,
            'grading_standard_id': None,
            'created_at': '2020-05-13T04:20:29Z',
            'updated_at': '2020-06-04T16:27:15Z',
            'peer_reviews': False,
            'automatic_peer_reviews': False,
            'position': 2,
            'grade_group_students_individually': False,
            'anonymous_peer_reviews': False,
            'group_category_id': None,
            'post_to_sis': False,
            'moderated_grading': False,
            'omit_from_final_grade': False,
            'intra_group_peer_reviews': False,
            'anonymous_instructor_annotations': False,
            'anonymous_grading': False,
            'graders_anonymous_to_graders': False,
            'grader_count': 0,
            'grader_comments_visible_to_graders': True,
            'final_grader_id': None,
            'grader_names_visible_to_final_grader': True,
            'allowed_attempts': -1,
            'secure_params': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJsdGlfYXNzaWdubWVudF9pZCI6IjViY2RhOWIyLWRjYjgtNGJiYi05MGEyLThhMjU5MDc0ZjU0NiJ9.QeXEAxoiRMZd9Mg7LKqoGx3oo2dl43oJsFSZAhHmk6o',
            'course_id': 2039048,
            'name': 'Jupyter home', #should worksheet_01, same as directory folder name.
            'submission_types': ['external_tool'],
            'has_submitted_submissions': False,
            'due_date_required': False,
            'max_name_length': 255,
            'in_closed_grading_period': False,
            'is_quiz_assignment': False,
            'can_duplicate': False,
            'original_course_id': None,
            'original_assignment_id': None,
            'original_assignment_name': None,
            'original_quiz_id': None,
            'workflow_state': 'published',
            'external_tool_tag_attributes': {'url': 'http://35.183.155.80/hub/lti/launch',
            'new_tab': True,
            'resource_link_id': 'a4deb4bfad23033c4a45c8412fa46d3a82cb13f7',
            'external_data': None,
            'content_type': 'ContextExternalTool',
            'content_id': 386958},
            'muted': True,
            'html_url': 'https://canvas.instructure.com/courses/2039048/assignments/15220351',
            'has_overrides': False,
            'url': 'https://canvas.instructure.com/api/v1/courses/2039048/external_tools/sessionless_launch?assignment_id=15220351&launch_type=assessment',
            'needs_grading_count': 0,
            'sis_assignment_id': None,
            'integration_id': None,
            'integration_data': {},
            'published': True,
            'unpublishable': True,
            'only_visible_to_overrides': False,
            'locked_for_user': False,
            'submissions_download_url': 'https://canvas.instructure.com/courses/2039048/assignments/15220351/submissions?zip=1',
            'post_manually': False,
            'anonymize_students': False,
            'require_lockdown_browser': False}
            '''

        self.all_submissions=[]
        self.client = docker.from_env()
        self.container = client.containers.get('45e6d2de7c54') #TODO what container?
        self.is_manual_grading_required = False #TA grading required? 

        #'unlock_at': '2020-05-12T06:00:00Z', #unlock date
        #'lock_at': '2020-11-29T06:59:59Z', #lock date
        self.is_unlocked = False  #before assignment is released - so that studet can click on the link
        self.is_locked   = False  #after assignment is locked - no longer accepting submissions
        #QUESTION: DIFFERENCE BETWEEN LOCKED & PASTDUE

        #'due_at': '2020-10-01T05:59:59Z', #due date
        self.is_past_due = False #after assignment due date

        #'has_submitted_submissions'
        #'in_closed_grading_period'
        self.is_grading = False #grading ongoing
        self.is_graded = False  #grading completed
        self.is_grade_collected = False #gradebook merged
        self.is_grade_posted = False #grades posted - assignment is done!

        #
        self.is_error = False # assignment of a submission of this assignment has an error
        self.error_msg = []

        #TODO add list of graders/instructors (could be the same person, but not necessarily) (cwl)


        def generate_assignment():
            
            return 0
        # TODO build the all_submissions list
        def collect_all_submissions(self):
            
            return 0

        # TODO assign graders
        def assign_graders(self):
            return 0

        # TODO copy student files to graders
        def copy_all_submissions(self):
            return 0

        def autograde_assignments():
            return 0
        def generate_feedback():
            return 0
        def generate_solution():
            return 0
        def return_feedback():
            return 0
        def return_solution():
            return 0
        def compute_max_score():
            return 0

        #QUESTIONS
        def backup_grades():
            return 0
        def backup_gradebooks():
            return 0

        #process ungraded assignments
        def process_new_assignments():
            return 0

        


    # TODO functions to figure out combinations of different flag status
        def set_is_unlocked(self):
            unlock_date    = parse_canvas_dates(assignment_info['unlock_at'])
            if datetime.datetime.today() > unlock_date:
                self.is_unlocked = True

        def set_is_past_due(self):
            due_date    = parse_canvas_dates(assignment_info['is_past_due'])
            if datetime.datetime.today() > due_date:
                self.is_past_due = True

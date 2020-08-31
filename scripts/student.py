from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool

class Student:

    # Class Attributes ?
        #TODO
        #shared path goes here

        
    # Instance Attributes
    def __init__(self):
         #TODO attributes in a dictionary
       
        #  {'id': 123459,
        #     'name': ' ',
        #     'created_at': '2020-05-13T19:03:24-06:00',
        #     'sortable_name': '',
        #     'short_name': ' ',
        #     'sis_user_id': None,
        #     'integration_id': None,
        #     'root_account': 'canvas.instructure.com',
        #     'login_id': 'blah@blah.com'}

        self.personal_info = {}
        self.submissions = []
        #gradebook?

        # Flags for various errors accumulated as the workflow script runs
        self.is_assignment_error = False
        self.is_script_error     = False
        self.is_docker_error     = False
        self.error_msg           = []

    # Getter Methods
    def get_submissions(self):
        #TODO
        return 0 


    #TODO
    # Post grade?
    

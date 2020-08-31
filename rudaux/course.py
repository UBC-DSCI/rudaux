#import posixpath
#import urllib.parse
#import requests
#import datetime
#import json

import os
from tqdm import tqdm
from git import Repo
from traitlets.config import Config
from traitlets.config.application import Application

class Course:
    """
    Course object for managing an entire Canvas/JupyterHub/nbgrader course.
    """

    def __init__(self, course_dir=None, auto=False):
    """Initialize a course from a config file. 
    :param course_dir: The directory your course. If none, defaults to current working directory. 
    :type course_dir: str
    :param auto: Suppress all prompts, automatically answering yes.
    :type auto: bool

    :returns: A Course object for performing operations on an entire course at once.
    :rtype: Course
    """

    #=======================================#
    #     Working Directory & Git Sync      #
    #=======================================#

    # Set up the working directory. If no course_dir has been specified, then it
    # is assumed that this is the course directory. 
    self.working_directory = course_dir if course_dir is not None else os.getcwd()
    
    repo = Repo(self.working_directory)

    # Before we do ANYTHING, make sure our working directory is clean with no
    # untracked files! Unless we're running a automated job, in which case we
    # don't want to fail for an unexpected reason.
    if (repo.is_dirty() or repo.untracked_files) and (not auto):
      continue_with_dirty = input(
        """
        Your repository is currently in a dirty state (modifications or
        untracked changes are present). We strongly suggest that you resolve
        these before proceeding. Continue? [y/n]:"""
      )
      # if they didn't say no, exit
      if continue_with_dirty.lower() != 'y':
        sys.exit("Exiting...")

    # PRINT BANNER
    print(AsciiTable([['Initializing Course and Pulling Instructors Repo']]).table)

    # pull the latest copy of the repo
    utils.pull_repo(repo_dir=self.working_directory)

    # Make sure we're running our nbgrader commands within our instructors repo.
    # this will contain our gradebook database, our source directory, and other
    # things.
    config = Config()
    config.CourseDirectory.root = self.working_directory

    #=======================================#
    #              Load Config              #
    #=======================================#

    # Check for an nbgrader config file...
    if not os.path.exists(os.path.join(self.working_directory, 'nbgrader_config.py')):
      # if there isn't one, make sure there's at least a rudaux config file
      if not os.path.exists(os.path.join(self.working_directory, 'rudaux_config.py')):
        sys.exit(
          """
          You do not have nbgrader_config.py or rudaux_config.py in your current
          directory. We need at least one of these to set up your course
          parameters! You can specify a directory with the course_dir argument
          if you wish.
          """
        )

    # use the traitlets Application class directly to load nbgrader config file.
    # reference:
    # https://github.com/jupyter/nbgrader/blob/41f52873c690af716c796a6003d861e493d45fea/nbgrader/server_extensions/validate_assignment/handlers.py#L35-L37

    # ._load_config_files() returns a generator, so if the config is missing,
    # the generator will act similarly to an empty array

    # load rudaux_config if it exists, otherwise just bring in nbgrader_config.
    for rudaux_config in Application._load_config_files('rudaux_config', path=self.working_directory):
      config.merge(rudaux_config)
    
    for nbgrader_config in Application._load_config_files('nbgrader_config', path=self.working_directory):
      config.merge(nbgrader_config)

    #=======================================#
    #           Set Config Params           #
    #=======================================#

    ## NBGRADER PARAMS

    # If the user set the exchange, perform home user expansion if necessary
    if config.get('Exchange', {}).get('root') is not None:
      # perform home user expansion. Should not throw an error, but may
      try:
        # expand home user in-place
        config['Exchange']['root'] = os.path.expanduser(config['Exchange']['root'])
      except:
        pass

    ## CANVAS PARAMS

    # Before we continue, make sure we have all of the necessary parameters.
    self.course_id = config.get('Canvas', {}).get('course_id')
    self.canvas_url = config.get('Canvas', {}).get('canvas_url')
    self.external_tool_name = config.get('Canvas', {}).get('external_tool_name')
    self.external_tool_level = config.get('Canvas', {}).get('external_tool_level')
    # The canvas url should have no trailing slash
    self.canvas_url = re.sub(r"/$", "", self.canvas_url)

    ## GITHUB PARAMS
    self.stu_repo_url = config.get('GitHub', {}).get('stu_repo_url', '')
    self.assignment_release_path = config.get('GitHub', {}).get('assignment_release_path')
    self.ins_repo_url = config.get('GitHub', {}).get('ins_repo_url')
    # subpath not currently supported
    # self.ins_dir_subpath = config.get('GitHub').get('ins_dir_subpath')
      
    ## JUPYTERHUB PARAMS

    self.hub_url = config.get('JupyterHub', {}).get('hub_url')
    # The hub url should have no trailing slash
    self.hub_url = re.sub(r"/$", "", self.hub_url)
    # Get Storage directory & type
    self.storage_path = config.get('JupyterHub', {}).get('storage_path', )
    self.zfs = config.get('JupyterHub', {}).get('zfs') # Optional, default is false!
    self.zfs_regex = config.get('JupyterHub', {}).get('zfs_regex') # default is false!
    self.zfs_datetime_pattern = config.get('JupyterHub', {}).get('zfs_datetime_pattern') # default is false!
    # Note hub_prefix, not base_url, to avoid any ambiguity
    self.hub_prefix = config.get('JupyterHub', {}).get('base_url')
    # If prefix was set, make sure it has no trailing slash, but a preceding
    # slash
    if self.hub_prefix is not None:
      self.hub_prefix = re.sub(r"/$", "", self.hub_prefix)
      if re.search(r"^/", self.hub_prefix) is None:
        self.hub_prefix = fr"/{self.hub_prefix}"

    ## COURSE PARAMS

    self.grading_image = config.get('Course', {}).get('grading_image')
    self.tmp_dir = config.get('Course', {}).get('tmp_dir')
    assignment_list = config.get('Course', {}).get('assignments')

    self.course_timezone = config.get('Course', {}).get('timezone')
    self.system_timezone = pendulum.now(tz='local').timezone.name

    ## Repurpose the rest of the params for later batches
    ## (Hang onto them in case we need something)

    self._full_config = config


        #1. Const for the course
        #Course Configuration Class Attributes
        #TODO not able to use a seperate config file
        hostname = Unicode(u'https://instructure.ubc.ca')#.tag(config=True)
        course_id = Int(2039048)#.tag(config=True)
        #course_token = Unicode(u'astring').tag(config=True)
        course_token = ""
        with open('token.txt') as reader:
              course_token = reader.read()

    #2. Dynamically updated as the course runs

    # people in the course
        students = [] #type: list
        teaching_assistants = [] #type: list
        instructors = [] #type: list
    # assignments in the course
        assignment = [] #type: list of Assignment objects


    #3. Flags for various errors accumulated as the workflow script runs
        is_assignment_error = False
        is_script_error     = False
        is_docker_error     = False
        error_msg           = [] #add error message as an entry in the list every time an error is caught.

        
    # Methods to Get Information from Canvas & Cache Them.
    # 1. Setting Everything Up, Helper Functions for 2.
        def generate_canvas_requests(self, requestURL):
            #e.g. requestURL = "https://canvas.instructure.com:443/api/v1/courses/2039048/students"
            #get from canvas site
            headers = {'Authorization' : 'Bearer ' + '%s' % self.course_token}
            #TODO  base url should be use hostname in config
            #TODO  posixpath.join("api", "v1", "courses", course['course_id'], "enrollments")
            #TODO  IMPORTANT: the while loop
            returned_request = requests.get(requestURL, headers = headers)
            returned_request_content = returned_request.content
            return returned_request_content

        def parse_canvas_response(self, raw_canvas_response):
            parsed_canvas_response = json.loads(raw_canvas_response)
            return parsed_canvas_response


    # # 2. Reading/Caching Data
    #     # maybe I can write the cached information to a json file
    #     # update the file when cron runs 
    #     # & read from the cached file when necessary
        def get_all_students(self):
            #TODO base url should be use hostname in config
            return self.generate_canvas_requests("https://canvas.instructure.com:443/api/v1/courses/2039048/students")

        def create_all_students(self,parsed_canvas_response):
            for curr_parsed_response in parsed_canvas_response:
                new_student = Student.Student()
                new_student.personal_info = curr_parsed_response
                #TODO all date items should get turned into a datetime object using parse_canvas_dates 
                self.students=self.students+[new_student]
            return self.students

    #     def get_all_TAs(self, course):
    #     def create_all_TAs():
    #     def get_all_instructors(self, course):
    #     def create_all_instructors():

        def get_all_assignments(self):
            #TODO base url should be use hostname in config
            return self.generate_canvas_requests("https://canvas.instructure.com:443/api/v1/courses/2039048/assignments")

        def create_all_assignments(self,parsed_canvas_response):
            for curr_parsed_response in parsed_canvas_response:
                new_assignment = Assignment.Assignment()
                new_assignment.assignment_info = curr_parsed_response
                #new_assignment = self.parse_canvas_assignment_dates(new_assignment)
                self.assignment_info=self.students+[new_assignment]
            return self.assignment


        def process_all_assignments():
            #get
            #create assignments in list
            #process each assignment in list
            return 0

        def dispatch():

            return 0




    # # Helper Functions for dispatch
        def parse_canvas_dates(raw_date_string):
            #str(st['created_at']).strip('Z').replace('T','-').replace(':','-')[:16]
            parsed_date_string = raw_date_string.strip('Z').replace('T','-').replace(':','-')[:16]
            #e.g. '2020-05-13-19-03'
            date_time_obj = datetime.datetime.strptime(parsed_date_string, '%Y-%m-%d-%H-%M')
            return date_time_obj
        
        def parse_canvas_assignment_dates(assignment_object):
            items = ['due_at','unlock_at','lock_at','created_at','updated_at']
            for item in items:
                print(assignment_object.assignment_info[item])
                #assignment_object.assignment_info[item] = parse_canvas_dates(assignment_object.assignment_info[item])
            return assignment_object

        def parse_canvas_student_dates(student_object):
            return 0

        def process_error_messages(self):
            #loop through all students
            #loop through all assignments
            #loop through all submissions

            #remove identical ones
            return 0

            
        def send_emails(self):
            #send notifications to instructors / graders
            email_hostname = '[SMTP_EMAIL_HOSTNAME]'
            email_address = '[EMAIL_ADDRESS]'
            email_username = '[SMTP_USERNAME]'
            email_pword = '[SMTP_PASSWORD]'
            print('Opening connection and logging in to email server')
            email_server = smtplib.SMTP(email_hostname)
            email_server.ehlo()
            email_server.starttls()
            email_server.login(email_username, email_pword)
            grader_message = '\r\n'.join(['From: '+email_address,
                                        'To: {}',
                                        'Subject: Manual grading needed',
                                        '',
                                        'Hi DSCI100 TA,',
                                        '',
                                        'You have an assigned manual grading task for assignments {} still open. Please log into our marking server and use the formgrader to grade these assignments.'
                                        '',
                                        'Thanks!',
                                        'DSCI100 Email Bot'])
            instructor_message = '\r\n'.join(['From: '+email_address,
                                        'To: {}',
                                        'Subject: Grading complete; checks needed',
                                        '',
                                        'Hi DSCI100 Instructor,',
                                        '',
                                        'Assignments {} now have all grades assigned. They are not yet posted; please visit Canvas to check the numbers and manually post them.',
                                        '',
                                        'Thanks!',
                                        'DSCI100 Email Bot'])
            for grader in grader_notifications.keys():
                print('Sending message to ' + grader + ' about grading ' + ', '.join(grader_notifications[grader]))
                email_server.sendmail(email_address, course['emails'][grader], grader_message.format(course['emails'][grader], ', '.join(grader_notifications[grader])))
            for instructor in instructor_notifications.keys():
                print('Sending message to ' + instructor + ' about posting grades for ' + ', '.join(instructor_notifications[instructor]))
                email_server.sendmail(email_address, course['emails'][instructor], instructor_message.format(course['emails'][instructor], ', '.join(instructor_notifications[instructor])))
                email_server.quit()
            
            return 0

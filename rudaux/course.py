#import posixpath
#import urllib.parse
#import requests
#import datetime
#import json

import os, sys
import pickle as pk
import tqdm
import pendulum as plm
import terminaltables as ttbl
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
from canvas import Canvas
import editdistance


#print(ttbl.AsciiTable([['Loading rudaux configuration']]).table)

class Course(object):
    """
    Course object for managing a Canvas/JupyterHub/nbgrader course.
    """

    def __init__(self, course_dir=None):
        """
        Initialize a course from a config file. 
        :param course_dir: The directory your course. If none, defaults to current working directory. 
        :type course_dir: str

        :returns: A Course object for performing operations on an entire course at once.
        :rtype: Course
        """

        if not course_dir:
            course_dir = os.getcwd()
        self.course_dir = course_dir

        #=======================================#
        #              Load Config              #
        #=======================================#
        
        print('Loading rudaux configuration')
        
        self.config = Config()

        if not os.path.exists(os.path.join(course_dir, 'rudaux_config.py')):
            sys.exit(
              """
              There is no rudaux_config.py in your current directory,
              and no course directory was specified on the command line. Please
              specify a directory with a valid rudaux_config.py file. 
              """
            )

        self.config.merge(PyFileConfigLoader('rudaux_config.py', path=course_dir).load_config())

        #=======================================#
        #    Open connection to notification    #
        #=======================================#

        #print('Opening a connection to the notifier')
        #self.notifier = self.config.notification_method(self)
        
        

        #================================================#
        #      Create object to interact with Canvas     #
        #================================================#

        print('Creating canvas interaction object')
        self.canvas = Canvas(self)

        #=======================================================#
        #      Create the course state  & populate info         #
        #=======================================================#

        state_filename = self.config.name + '_state.pk'
        print('Checking for saved course state file at ' + state_filename)

        if os.path.exists(state_filename):
            print('Saved state exists. Loading')
            state = None
            with open(state_filename, 'rb') as f:
                state = pk.load(f)

            self.students = state['students']
            self.fake_students = state['fake_students']
            self.teachers = state['teachers']
            self.tas = state['tas']
            self.submissions = state['submissions']
            self.assignments = state['assignments']
        else:
            print('No saved state exists. Collecting information from Canvas...')
            self.students, self.tas, self.teachers, self.fake_students, self.assignments, self.submissions = self.get_canvas_state()
            #TODO self.get_jupyterhub_state()
        
    def close_notifier(self):
        self.notifier.close()

    def save_state(self):
        with open(state_filename, 'wb') as f:
            pk.dump(f, {'students' : self.students,
                        'fake_students' : self.fake_students,
                        'teachers' : self.teachers,
                        'tas' : self.tas,
                        'assignments' : self.assignments,
                        'submissions' : self.submissions
                        })

    def get_canvas_state(self):
        print('No saved state exists. Collecting information from Canvas...')
        print('Obtaining student enrollment information...')
        student_dicts = self.canvas.get_students()
        print('Obtaining TA enrollment information...')
        ta_dicts = self.canvas.get_tas()
        print('Obtaining teacher enrollment information...')
        teacher_dicts = self.canvas.get_teachers()
        print('Obtaining student view / fake student enrollment information...')
        fake_student_dicts = self.canvas.get_fake_students()
        print('Obtaining assignment information...')
        assignment_dicts = self.canvas.get_assignments()

        #TODO create objects
        self.students = []
        self.tas = []
        self.teachers = []
        self.fake_students = []
        self.assignments = []
        self.submissions = []


    def get_jupyterhub_state(self):
        pass

    def get_canvas_diff(self):
    
    def get_jupyterhub_diff(self):

    def synchronize_canvas(self):
        pass
    
    def synchronize_jupyterhub(self):
        pass
    
    def synchronize(self):

    def get_status(self):
        pass

    def search_students(self, name = None, canvas_id = None, sis_id = None, max_return = 5):
        #get exact matches for IDs
        match = [s for s in self.students if s.canvas_id == canvas_id]
        match.extend([s for s in self.students if s.sis_id == sis_id])

        #get fuzzy match for name
        def normalize_name(nm):
            return ''.join([ch for ch in nm.lower() if ch.isalnum()])
        name_key = normalize_name(name)
        fuzzy_match_name = []
        for s in self.students:
            forward_key = normalize_name(s.sortable_name)
            backward_key = normalize_name(''.join(s.sortable_name.split(',')[::-1]))
            dist = min(editdistance.eval(name_key, forward_key), editdistance.eval(name_key, backward_key))
            fuzzy_match_name.append((s, dist))
        match.extend(sorted(fuzzy_match_name, key = lambda x : x[1])[:max_return])

        #return unique identical entries
        return list(set(match))[:max_return]

    ##2. Dynamically updated as the course runs

    ## people in the course
    #    students = [] #type: list
    #    teaching_assistants = [] #type: list
    #    instructors = [] #type: list
    ## assignments in the course
    #    assignment = [] #type: list of Assignment objects


    ##3. Flags for various errors accumulated as the workflow script runs
    #    is_assignment_error = False
    #    is_script_error     = False
    #    is_docker_error     = False
    #    error_msg           = [] #add error message as an entry in the list every time an error is caught.

    #    
    ## Methods to Get Information from Canvas & Cache Them.
    ## 1. Setting Everything Up, Helper Functions for 2.
    #def generate_canvas_requests(self, requestURL):
    #    #e.g. requestURL = "https://canvas.instructure.com:443/api/v1/courses/2039048/students"
    #    #get from canvas site
    #    headers = {'Authorization' : 'Bearer ' + '%s' % self.course_token}
    #    #TODO  base url should be use hostname in config
    #    #TODO  posixpath.join("api", "v1", "courses", course['course_id'], "enrollments")
    #    #TODO  IMPORTANT: the while loop
    #    returned_request = requests.get(requestURL, headers = headers)
    #    returned_request_content = returned_request.content
    #    return returned_request_content

    #def parse_canvas_response(self, raw_canvas_response):
    #    parsed_canvas_response = json.loads(raw_canvas_response)
    #    return parsed_canvas_response


    ## # 2. Reading/Caching Data
    ##     # maybe I can write the cached information to a json file
    ##     # update the file when cron runs 
    ##     # & read from the cached file when necessary
    #def get_all_students(self):
    #    #TODO base url should be use hostname in config
    #    return self.generate_canvas_requests("https://canvas.instructure.com:443/api/v1/courses/2039048/students")

    #def create_all_students(self,parsed_canvas_response):
    #    for curr_parsed_response in parsed_canvas_response:
    #        new_student = Student.Student()
    #        new_student.personal_info = curr_parsed_response
    #        #TODO all date items should get turned into a datetime object using parse_canvas_dates 
    #        self.students=self.students+[new_student]
    #    return self.students

    ##     def get_all_TAs(self, course):
    ##     def create_all_TAs():
    ##     def get_all_instructors(self, course):
    ##     def create_all_instructors():

    #def get_all_assignments(self):
    #    #TODO base url should be use hostname in config
    #    return self.generate_canvas_requests("https://canvas.instructure.com:443/api/v1/courses/2039048/assignments")

    #def create_all_assignments(self,parsed_canvas_response):
    #    for curr_parsed_response in parsed_canvas_response:
    #        new_assignment = Assignment.Assignment()
    #        new_assignment.assignment_info = curr_parsed_response
    #        #new_assignment = self.parse_canvas_assignment_dates(new_assignment)
    #        self.assignment_info=self.students+[new_assignment]
    #    return self.assignment


    #def process_all_assignments():
    #    #get
    #    #create assignments in list
    #    #process each assignment in list
    #    return 0

    #def dispatch():

    #    return 0

    ## # Helper Functions for dispatch
    #def parse_canvas_dates(raw_date_string):
    #    #str(st['created_at']).strip('Z').replace('T','-').replace(':','-')[:16]
    #    parsed_date_string = raw_date_string.strip('Z').replace('T','-').replace(':','-')[:16]
    #    #e.g. '2020-05-13-19-03'
    #    date_time_obj = datetime.datetime.strptime(parsed_date_string, '%Y-%m-%d-%H-%M')
    #    return date_time_obj
    #
    #def parse_canvas_assignment_dates(assignment_object):
    #    items = ['due_at','unlock_at','lock_at','created_at','updated_at']
    #    for item in items:
    #        print(assignment_object.assignment_info[item])
    #        #assignment_object.assignment_info[item] = parse_canvas_dates(assignment_object.assignment_info[item])
    #    return assignment_object

    #def parse_canvas_student_dates(student_object):
    #    return 0

    #def process_error_messages(self):
    #    #loop through all students
    #    #loop through all assignments
    #    #loop through all submissions

    #    #remove identical ones
    #    return 0

    #    
    #def send_emails(self):
    #    #send notifications to instructors / graders
    #    email_hostname = '[SMTP_EMAIL_HOSTNAME]'
    #    email_address = '[EMAIL_ADDRESS]'
    #    email_username = '[SMTP_USERNAME]'
    #    email_pword = '[SMTP_PASSWORD]'
    #    print('Opening connection and logging in to email server')
    #    email_server = smtplib.SMTP(email_hostname)
    #    email_server.ehlo()
    #    email_server.starttls()
    #    email_server.login(email_username, email_pword)
    #    grader_message = '\r\n'.join(['From: '+email_address,
    #                                'To: {}',
    #                                'Subject: Manual grading needed',
    #                                '',
    #                                'Hi DSCI100 TA,',
    #                                '',
    #                                'You have an assigned manual grading task for assignments {} still open. Please log into our marking server and use the formgrader to grade these assignments.'
    #                                '',
    #                                'Thanks!',
    #                                'DSCI100 Email Bot'])
    #    instructor_message = '\r\n'.join(['From: '+email_address,
    #                                'To: {}',
    #                                'Subject: Grading complete; checks needed',
    #                                '',
    #                                'Hi DSCI100 Instructor,',
    #                                '',
    #                                'Assignments {} now have all grades assigned. They are not yet posted; please visit Canvas to check the numbers and manually post them.',
    #                                '',
    #                                'Thanks!',
    #                                'DSCI100 Email Bot'])
    #    for grader in grader_notifications.keys():
    #        print('Sending message to ' + grader + ' about grading ' + ', '.join(grader_notifications[grader]))
    #        email_server.sendmail(email_address, course['emails'][grader], grader_message.format(course['emails'][grader], ', '.join(grader_notifications[grader])))
    #    for instructor in instructor_notifications.keys():
    #        print('Sending message to ' + instructor + ' about posting grades for ' + ', '.join(instructor_notifications[instructor]))
    #        email_server.sendmail(email_address, course['emails'][instructor], instructor_message.format(course['emails'][instructor], ', '.join(instructor_notifications[instructor])))
    #        email_server.quit()
    #    
    #    return 0

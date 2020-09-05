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

    def jupyterhub_snapshot(self):
        for s in self.students:
            pass

    def get_jupyterhub_state(self):
        pass

    def get_canvas_diff(self):
        pass
    
    def get_jupyterhub_diff(self):
        pass

    def synchronize_canvas(self):
        pass
    
    def synchronize_jupyterhub(self):
        pass
    
    def synchronize(self):
        pass

    def get_status(self):
        pass

    def get_notifications(self):
        pass

    def send_notifications(self):
        pass

    def resolve_notification(self):
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

    

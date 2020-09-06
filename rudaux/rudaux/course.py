import os, sys
import pickle as pk
import tqdm
import pendulum as plm
import terminaltables as ttbl
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import editdistance
import namedtuple
from .canvas import Canvas
from .jupyterhub import JupyterHub

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
        #          Validate Config              #
        #=======================================#
        #make sure the student folder root doesn't end with a slash (for careful zfs snapshot syntax)
        self.config.jupyterhub_user_folder_root.rstrip('/')

        
        #================================================================#
        #      Create objects to interact with Canvas and JupyterHub     #
        #================================================================#

        print('Creating Canvas interaction object')
        self.canvas = Canvas(self)

        print('Creating JupyterHub interaction object')
        self.jupyterhub = JupyterHub(self)

        #=======================================================#
        #      Create the course state  & populate info         #
        #=======================================================#

        state_filename = os.path.join(self.course_dir, self.config.name + '_state.pk')
        print('Checking for saved course state file at ' + state_filename)

        if os.path.exists(state_filename):
            print('Saved state exists. Loading')
            saved_course = None
            with open(state_filename, 'rb') as f:
                saved_course = pk.load(f)

            self.students = saved_course['students']
            self.fake_students = saved_course['fake_students']
            self.teachers = saved_course['teachers']
            self.tas = saved_course['tas']
            self.assignments = saved_course['assignments']
            self.submissions = saved_course['submissions']
        else:
            print('No saved state exists. Collecting information from Canvas/JupyterHub...')

            print('Obtaining/processing student enrollment information from Canvas...')
            student_dicts = self.canvas.get_students()
            self.students = [Person(sd) for sd in student_dicts]

            print('Obtaining/processing TA enrollment information from Canvas...')
            ta_dicts = self.canvas.get_tas()
            self.tas = [Person(tad) for tad in ta_dicts]

            print('Obtaining/processing teacher enrollment information from Canvas...')
            teacher_dicts = self.canvas.get_teachers()
            self.teachers = [Person(td) for td in teacher_dicts]

            print('Obtaining/processing student view / fake student enrollment information from Canvas...')
            fake_student_dicts = self.canvas.get_fake_students()
            self.fake_students = [Person(fd) for fd in fake_student_dicts]

            print('Obtaining/processing assignment information from Canvas...')
            assignment_dicts = self.canvas.get_assignments()
            self.assignments = [Assignment(ad) for ad in assignment_dicts]

            print('Obtaining submission information from Canvas...')
            #self.submissions = []
            #for a in self.assignments:
            #    #if any due date is passed
            #    for s in self.students:
            #        #create a subm object and add it to the global list, and lists for that student and assignment
            #        Submission()
            #        #add it t
            #        canvas_submission_dicts = self.canvas.todo()
            #        print('Obtaining local submission information from JupyterHub...')
            #        jupyterhub_submission_dicts = self.jupyterhub.todo()
            #        #TODO
        
    def save_state(self, state_filename = None):
        if state_filename is None:
            state_filename = os.path.join(self.course_dir, self.config.name + '_state.pk')

        with open(state_filename, 'wb') as f:
            pk.dump(f, {'students' : self.students,
                        'fake_students' : self.fake_students,
                        'teachers' : self.teachers,
                        'tas' : self.tas,
                        'assignments' : self.assignments,
                        'submissions' : self.submissions
                        })

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
        #print('Opening a connection to the notifier')
        #self.notifier = self.config.notification_method(self)

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

    

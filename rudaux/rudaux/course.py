import os, sys
import pickle as pk
import tqdm
import pendulum as plm
import terminaltables as ttbl
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import editdistance
from .canvas import Canvas
from .jupyterhub import JupyterHub
from .person import Person
from .assignment import Assignment

class MultipleOverrideError(Exception):
    def __init__(self, overrides, sname, aname):
        self.overrides = overrides
        self.sname = sname
        self.aname = aname

class GroupOverrideError(Exception):
    def __init__(self, override, snames, aname):
        self.override = override
        self.snames = snames
        self.aname = aname


class Course(object):
    """
    Course object for managing a Canvas/JupyterHub/nbgrader course.
    """

    def __init__(self, course_dir):
        """
        Initialize a course from a config file. 
        :param course_dir: The directory your course. If none, defaults to current working directory. 
        :type course_dir: str

        :returns: A Course object for performing operations on an entire course at once.
        :rtype: Course
        """

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

            self.course_info = saved_course['course_info']
            self.students = saved_course['students']
            self.fake_students = saved_course['fake_students']
            self.instructors = saved_course['instructors']
            self.tas = saved_course['tas']
            self.assignments = saved_course['assignments']
            self.submissions = saved_course['submissions']
        else:
            print('No saved state exists. Collecting information from Canvas/JupyterHub...')
            self.synchronize()
        
    def save_state(self, no_clobber = False, state_filename = None):
        if state_filename is None:
            state_filename = os.path.join(self.course_dir, self.config.name + '_state.pk')

        print('Saving state to file ' + state_filename)

        if no_clobber and os.path.exists(state_filename):
            print('State file exists and no_clobber = True; returning')
            return
            
        with open(state_filename, 'wb') as f:
            pk.dump({   'course_info' : self.course_info,
                        'students' : self.students,
                        'fake_students' : self.fake_students,
                        'instructors' : self.instructors,
                        'tas' : self.tas,
                        'assignments' : self.assignments,
                        'submissions' : self.submissions
                        }, f)
        return

    def synchronize(self):
        self.synchronize_canvas()
        self.synchronize_jupyterhub()

    def synchronize_canvas(self):
        print('Obtaining course information...')
        self.course_info = self.canvas.get_course_info()
        
        print('Obtaining/processing student enrollment information from Canvas...')
        student_dicts = self.canvas.get_students()
        self.students = [Person(sd) for sd in student_dicts]

        print('Obtaining/processing TA enrollment information from Canvas...')
        ta_dicts = self.canvas.get_tas()
        self.tas = [Person(tad) for tad in ta_dicts]

        print('Obtaining/processing instructor enrollment information from Canvas...')
        instructor_dicts = self.canvas.get_instructors()
        self.instructors = [Person(ind) for ind in instructor_dicts]

        print('Obtaining/processing student view / fake student enrollment information from Canvas...')
        fake_student_dicts = self.canvas.get_fake_students()
        self.fake_students = [Person(fd) for fd in fake_student_dicts]

        print('Obtaining/processing assignment information from Canvas...')
        assignment_dicts = self.canvas.get_assignments()
        self.assignments = [Assignment(ad) for ad in assignment_dicts]

        print('Obtaining submission information from Canvas...')
        self.submissions = []
        #for a in self.assignments:
        #    #if any due date is passed
        #    for s in self.students:
        #        #create a subm object and add it to the global list, and lists for that student and assignment
        #        Submission()
        #        #add it t
        return
    
    def synchronize_jupyterhub(self):
        return

    def apply_latereg_extensions(self):
        print('Applying late registration extensions')
        for a in self.assignments:
            if a['due_at']: #if the assignment has a due date set
                for s in self.students:
                    #if student s registered after assignment a was unlocked
                    if s.reg_updated > a.unlock_at:
                        print('Student ' + s.name + ' registration date (' + str(s.reg_updated.in_timezone(self.course_info['time_zone']))+') after unlock date of assignment ' + a.name + ' (' + str(a.unlock_at.in_timezone(self.course_info['time_zone'])) + ')')
                        #check if this student already has an override for this assignment (instructor may have added one manually)
                        #if yes and it's earlier than latereg extension, remove the override and check removal
                        #if yes and it's later, keep the later one (in favour of student)
                        a_s_overrides = [(idx, over) for idx, over in enumerate(a.overrides) if s.canvas_id in over['student_ids'] and over['due_at']]
                        #make sure this student doesn't appear in multiple overrides for this assignment
                        if len(a_s_overrides) > 1:
                            raise MultipleOverrideError(a_s_overrides, s.name, a.name)
                        if len(a_s_overrides) == 1:
                            print('Student has previous override for this assignment')
                            #student already has an override
                            idx  = a_s_overrides[0][0]
                            over = a_s_overrides[0][1]
                            #make sure this override isn't a group override
                            if len(over['student_ids']) > 1:
                                raise GroupOverrideError(over, over['student_ids'], a.name) 
                            #get the due date
                            prev_override_due_at = over['due_at']
                            prev_override_id = over['id']
                            #if it is after the late reg extension, do nothing; otherwise, delete it before creating a new one
                            if prev_override_due_at > s.reg_updated.add(days=7):
                                print('Previous override (' + str(prev_override_due_at.in_timezone(self.course_info['time_zone'])) + ') is after late reg date. Skipping...')
                                continue
                            else:
                                print('Previous override (' + str(prev_override_due_at.in_timezone(self.course_info['time_zone'])) + ') is before late reg date. Removing...')
                                self.canvas.remove_override(a.canvas_id, prev_override_id)
                        print('Creating late registration override (' + str(s.reg_updated.add(days=7).in_timezone(self.course_info['time_zone'])) + ')')
                        self.canvas.create_override(a.canvas_id, {'student_ids' : [s.canvas_id],
                                                                  'due_at' : s.reg_updated.add(days=7),
                                                                  'lock_at' : a.lock_at,
                                                                  'unlock_at' : a.unlock_at,
                                                                  'title' : s.name+'-'+a.name+'-late-registration'}
                                                   )
        return 

    def jupyterhub_snapshot(self):
        for s in self.students:
            pass

    def get_jupyterhub_state(self):
        pass

    def get_canvas_diff(self):
        pass
    
    def get_jupyterhub_diff(self):
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

    

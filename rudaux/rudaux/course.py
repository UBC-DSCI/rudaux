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

class DuplicateError(Exception):
    def __init__(self, key, matches):
        self.key = key
        self.matches = matches


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
            
            self.students = []
            self.fake_students = []
            self.instructors = []
            self.tas = []
            self.assignments = []
            self.submissions = [] 

            self.synchronize()
        print('Done.')
        
    def save_state(self, no_clobber = False, state_filename = None):
        if state_filename is None:
            state_filename = os.path.join(self.course_dir, self.config.name + '_state.pk')

        print('Saving state to file ' + state_filename)

        if no_clobber and os.path.exists(state_filename):
            print('State file exists and no_clobber requested; returning without saving to disk')
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
        print('Done.')
        return

    def synchronize(self):
        self.synchronize_canvas()
        self.synchronize_jupyterhub()

    def _update_canvas_items(self, newitems, items, item_cls):
        for newitem in newitems:
            matches = [item for item in items if newitem['canvas_id'] == item.canvas_id]
            if len(matches) > 1:
                raise DuplicateError(newitem, matches)
            elif len(matches) == 1:
                matches[0].canvas_update(newitem)
            else:
                items.append(item_cls(newitem))

    def synchronize_canvas(self):
        print('Obtaining course information...')
        self.course_info = self.canvas.get_course_info()
        print('Done.')
        
        print('Obtaining/processing student enrollment information from Canvas...')
        student_dicts = self.canvas.get_students()
        self._update_canvas_items(student_dicts, self.students, Person)
        print('Done.')

        print('Obtaining/processing TA enrollment information from Canvas...')
        ta_dicts = self.canvas.get_tas()
        self._update_canvas_items(ta_dicts, self.tas, Person)
        print('Done.')

        print('Obtaining/processing instructor enrollment information from Canvas...')
        instructor_dicts = self.canvas.get_instructors()
        self._update_canvas_items(instructor_dicts, self.instructors, Person)
        print('Done.')

        print('Obtaining/processing student view / fake student enrollment information from Canvas...')
        fake_student_dicts = self.canvas.get_fake_students()
        self._update_canvas_items(fak_student_dicts, self.fake_students, Person)
        print('Done.')

        print('Obtaining/processing assignment information from Canvas...')
        assignment_dicts = self.canvas.get_assignments()
        self._update_canvas_items(assignment_dicts, self.assignments, Assignment)
        print('Done.')
        return
    
    def synchronize_jupyterhub(self):
        return

    def apply_latereg_extensions(self):
        print('Applying late registration extensions')
        for a in self.assignments:
            if a['due_at']: #if the assignment has a due date set
                for s in self.students:
                    regdate = s.reg_updated if s.reg_updated else s.reg_created
                    if s.status == 'active' and regdate > a.unlock_at:
                        #if student s active and registered after assignment a was unlocked
                        print('Student ' + s.name + ' registration date (' + str(regdate.in_timezone(self.course_info['time_zone']))+') after unlock date of assignment ' + a.name + ' (' + str(a.unlock_at.in_timezone(self.course_info['time_zone'])) + ')')
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
                            if prev_override_due_at >= regdate.add(days=7):
                                print('Previous override (' + str(prev_override_due_at.in_timezone(self.course_info['time_zone'])) + ') is after late reg date. Skipping...')
                                continue
                            else:
                                print('Previous override (' + str(prev_override_due_at.in_timezone(self.course_info['time_zone'])) + ') is before late reg date. Removing...')
                                self.canvas.remove_override(a.canvas_id, prev_override_id)
                                #TODO remove override in the canvas course state
                        print('Creating late registration override (' + str(regdate.add(days=7).in_timezone(self.course_info['time_zone'])) + ')')
                        self.canvas.create_override(a.canvas_id, {'student_ids' : [s.canvas_id],
                                                                  'due_at' : regdate.add(days=7),
                                                                  'lock_at' : a.lock_at,
                                                                  'unlock_at' : a.unlock_at,
                                                                  'title' : s.name+'-'+a.name+'-late-registration'}
                                                   )
        print('Done.')
        return 

    def jupyterhub_snapshot(self):
        print('Taking snapshots')
        for a in self.assignments:
            if a.due_at < plm.now() and not a.snapshot_taken:
                print('Assignment ' + a.name + ' is past due (due at ' + str(a.due_at.in_timezone(self.course_info['time_zone'])) + ', time now ' +  str(plm.now().in_timezone(self.course_info['time_zone'])) ') and no snapshot exists yet. Taking a snapshot...')
                self.jupyterhub.snapshot_all(a.name)
                a.snapshot_taken = True
            for over in a.overrides:
                if over['due_at'] < plm.now() and not (over['id'] in a.override_snapshots_taken):
                    print('Assignment ' + a.name + ' has an override for student ' + over['student_ids'][0] + ' (due at ' + str(over['due_at'].in_timezone(self.course_info['time_zone'])) + ', time now ' +  str(plm.now().in_timezone(self.course_info['time_zone'])) ') and no snapshot exists yet. Taking a snapshot...')
                    self.jupyterhub.snapshot_user(over['student_ids'][0], a.name + '-' + plm.now().format('YYYY-mm-dd-HH-mm-ss'))
                    a.override_snapshots_taken.append(over['id'])
        print('Done.')

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

    

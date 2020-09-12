import os, sys
import pickle as pk
import tqdm
import pendulum as plm
import terminaltables as ttbl
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import editdistance
from subprocess import CalledProcessError
from .canvas import Canvas
from .jupyterhub import JupyterHub
from .zfs import ZFS
from .person import Person
from .assignment import Assignment
from .dockergrader import DockerGrader


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

    def __init__(self, course_dir, dry_run = False, allow_canvas_cache = False):
        """
        Initialize a course from a config file. 
        :param course_dir: The directory your course. If none, defaults to current working directory. 
        :type course_dir: str

        :returns: A Course object for performing operations on an entire course at once.
        :rtype: Course
        """

        self.course_dir = course_dir
        self.dry_run = dry_run

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
        
        #===================================================================================================#
        #      Create Canvas object and try to load state (if failure, load cached if we're allowed to)     #
        #===================================================================================================#

        print('Creating Canvas interface...')
        self.canvas = Canvas(self)
        self.canvas_cache_filename = os.path.join(self.course_dir, self.config.name + '_canvas_cache.pk')
        self.synchronize_canvas(allow_canvas_cache)
        
        #=======================================================#
        #      Load the jupyterhub state & populate info        #
        #=======================================================#

        print('Creating JupyterHub interface...')
        self.jupyterhub = JupyterHub(self)
        self.jupyterhub_cache_filename = os.path.join(self.course_dir, self.config.name + '_jupyterhub_cache.pk')
        self.load_jupyterhub_state()


        #=======================================================#
        #      Create the interface to ZFS                      #
        #=======================================================#

        print('Creating ZFS interface...')
        self.jupyterhub = JupyterHub(self)
        self.jupyterhub_cache_filename = os.path.join(self.course_dir, self.config.name + '_jupyterhub_cache.pk')
        self.load_jupyterhub_state()

        #=======================================================#
        #      Create the interface to Docker                   #
        #=======================================================#

        print('Creating Docker interface...')
        self.jupyterhub = JupyterHub(self)
        self.jupyterhub_cache_filename = os.path.join(self.course_dir, self.config.name + '_jupyterhub_cache.pk')
        self.load_jupyterhub_state()


        
        print('Done.')
        
    #def save_state(self, no_clobber = False, state_filename = None):
    #    if state_filename is None:
    #        state_filename = os.path.join(self.course_dir, self.config.name + '_state.pk')

    #    print('Saving state to file ' + state_filename)

    #    if no_clobber and os.path.exists(state_filename):
    #        print('State file exists and no_clobber requested; returning without saving to disk')
    #        return
    #        
    #    with open(state_filename, 'wb') as f:
    #        pk.dump({   'course_info' : self.course_info,
    #                    'students' : self.students,
    #                    'fake_students' : self.fake_students,
    #                    'instructors' : self.instructors,
    #                    'tas' : self.tas,
    #                    'assignments' : self.assignments,
    #                    'submissions' : self.submissions
    #                    }, f)
    #    print('Done.')
    #    return

    #def synchronize(self):
    #    self.synchronize_canvas()
    #    self.synchronize_jupyterhub()

    #def _update_canvas_items(self, newitems, items, item_cls):
    #    for newitem in newitems:
    #        matches = [item for item in items if newitem['canvas_id'] == item.canvas_id]
    #        if len(matches) > 1:
    #            raise DuplicateError(newitem, matches)
    #        elif len(matches) == 1:
    #            matches[0].canvas_update(newitem)
    #        else:
    #            items.append(item_cls(newitem))

    def synchronize_canvas(self, allow_cache = False):
        try:
            print('Synchronizing with Canvas...')

            print('Obtaining course information...')
            self.course_info = self.canvas.get_course_info()
            print('Done.')
            
            print('Obtaining/processing student enrollment information from Canvas...')
            student_dicts = self.canvas.get_students()
            self.students = [Person(sd) for sd in student_dicts]
            print('Done.')

            print('Obtaining/processing TA enrollment information from Canvas...')
            ta_dicts = self.canvas.get_tas()
            self.tas = [Person(ta) for ta in ta_dicts]
            print('Done.')

            print('Obtaining/processing instructor enrollment information from Canvas...')
            instructor_dicts = self.canvas.get_instructors()
            self.instructors = [Person(inst) for inst in instructor_dicts]
            print('Done.')

            print('Obtaining/processing student view / fake student enrollment information from Canvas...')
            fake_student_dicts = self.canvas.get_fake_students()
            self.fake_students = [Person(fsd) for fsd in fake_student_dicts]
            print('Done.')

            print('Obtaining/processing assignment information from Canvas...')
            assignment_dicts = self.canvas.get_assignments()
            self.assignments = [Assignment(ad) for ad in assignment_dicts]
            print('Done.')
        except Exception as e:
            print('Exception encountered during synchronization')
            print(e)
            if allow_canvas_cache:
                print('Attempting to fall back to cache...')
                if os.path.exists(self.canvas_cache_filename):
                    print('Loading cached canvas state from ' + self.canvas_cache_filename)
                    canvas_cache = None
                    with open(self.canvas_cache_filename, 'rb') as f:
                        canvas_cache = pk.load(f)
                    self.course_info = canvas_cache['course_info']
                    self.students = canvas_cache['students']
                    self.fake_students = canvas_cache['fake_students']
                    self.instructors = canvas_cache['instructors']
                    self.tas = canvas_cache['tas']
                    self.assignments = canvas_cache['assignments']
        else:
            print('Saving canvas cache file...')
            with open(self.canvas_cache_filename, 'wb') as f:
                pk.dump({'course_info' : self.course_info,
                         'students' : self.students,
                         'fake_students' : self.fake_students,
                         'instructors' : self.instructors,
                         'tas' : self.tas,
                         'assignments' : self.assignments,
                         }, f)
        return
    
    def load_jupyterhub_state(self):
        print('Loading the JupyterHub state...')
        
        if os.path.exists(self.jupyterhub_cache_filename):
            with open(self.jupyterhub_cache_filename, 'rb') as f:
                self.submissions, self.snapshots = pk.load(f)
        else: 
            print('No cache file found. Initializing empty state.')
            self.submissions = {}
            self.snapshots = []

        return
    
    def save_jupyterhub_state(self):
        print('Saving the JupyterHub state...')
        if not self.dry_run:
            with open(self.jupyterhub_cache_filename, 'wb') as f:
                pk.dump((self.submissions, self.snapshots), f)
            print('Done.')
        else:
            print('[Dry Run: state not saved]')
        return

    def jupyterhub_snapshot(self):
        print('Taking snapshots')
        for a in self.assignments:
            if a.due_at and a.due_at < plm.now() and a.name not in self.snapshots:
                print('Assignment ' + a.name + ' is past due and no snapshot exists yet. Taking a snapshot [' + a.name + ']')
                try:
                    self.jupyterhub.snapshot_all(a.name)
                except CalledProcessError as e:
                    print('Error creating snapshot ' + a.name)
                    print('Return code ' + str(e.returncode))
                    print(e.output.decode('utf-8'))
                    print('Not updating the taken snapshots list')
                else:
                    if not self.dry_run:
                        self.snapshots.append(a.name)
                    else:
                        print('[Dry Run: snapshot name not added to taken list; would have added ' + a.name + ']')
            for over in a.overrides:
                snapname = a.name + '-override-' + over['id']
                if over['due_at'] and over['due_at'] < plm.now() and not (snapname in self.snapshots):
                    print('Assignment ' + a.name + ' has override ' + over['id'] + ' for student ' + over['student_ids'][0] + ' and no snapshot exists yet. Taking a snapshot [' + snapname + ']')
                    add_to_taken_list = True
                    try:
                        self.jupyterhub.snapshot_user(over['student_ids'][0], snapname)
                    except CalledProcessError as e:
                        print('Error creating snapshot ' + snapname)
                        print('Return code ' + str(e.returncode))
                        print(e.output.decode('utf-8'))
                        if 'dataset does not exist' not in e.output.decode('utf-8'):
                            print('Unknown error; not updating the taken snapshots list')
                            add_to_taken_list = False
                        else:
                            print('Student hasnt created their folder; this counts as a missing submission. Updating taken snapshots list.')

                    if not self.dry_run and add_to_taken_list:
                        self.snapshots.append(snapname)
                    elif self.dry_run:
                        print('[Dry Run: snapshot name not added to taken list; would have added ' + snapname + ']')
        print('Done.')
        self.save_jupyterhub_state()

    #TODO Add dry-run logic here
    def apply_latereg_extensions(self, extdays):
        need_synchronize = False
        print('Applying late registration extensions')
        for a in self.assignments:
            if a.due_at and a.unlock_at: #if the assignment has both a due date and unlock date set
                print('Checking ' + str(a.name))
                for s in self.students:
                    regdate = s.reg_updated if s.reg_updated else s.reg_created
                    if s.status == 'active' and regdate > a.unlock_at:
                        #if student s active and registered after assignment a was unlocked
                        print('Student ' + s.name + ' registration date (' + str(regdate.in_timezone(self.course_info['time_zone']))+') after unlock date of assignment ' + a.name + ' (' + str(a.unlock_at.in_timezone(self.course_info['time_zone'])) + ')')
                        #the common due date
                        basic_date = a.due_at
                        #the late registration due date
                        latereg_date = regdate.add(days=extdays)
                        if latereg_date > basic_date:
                            print('This will cause an automatic late registration extension to ' + str(latereg_date.in_timezone(self.course_info['time_zone'])) + ' unless there are existing overrides. Checking...')
                            #get the date from a possibly existing override
                            a_s_overrides = [(idx, over) for idx, over in enumerate(a.overrides) if s.canvas_id in over['student_ids'] and over['due_at']]
                            if len(a_s_overrides) > 1:
                                raise MultipleOverrideError(a_s_overrides, s.name, a.name)
                            if len(a_s_overrides) == 1:
                                #student already has an override
                                idx  = a_s_overrides[0][0]
                                over = a_s_overrides[0][1]
                                #make sure this override isn't a group override
                                if len(over['student_ids']) > 1:
                                    raise GroupOverrideError(over, over['student_ids'], a.name) 
                                #get the due date
                                override_date = over['due_at']
                                override_id = over['id']
                                print('Student has previous override extension for this assignment to ' + str(override_date.in_timezone(self.course_info['time_zone'])))
                                #if it is after the late reg extension, do nothing; otherwise, delete it before creating a new one
                                if override_date >= latereg_date:
                                    print('Previous override is after late reg date. Skipping...')
                                    continue
                                else:
                                    print('Previous override is before late reg date. Removing...')
                                    self.canvas.remove_override(a.canvas_id, override_id)
                            print('Creating late registration override')
                            need_synchronize = True
                            self.canvas.create_override(a.canvas_id, {'student_ids' : [s.canvas_id],
                                                                  'due_at' : latereg_date,
                                                                  'lock_at' : a.lock_at,
                                                                  'unlock_at' : a.unlock_at,
                                                                  'title' : s.name+'-'+a.name+'-latereg'}
                                                   )
                        else:
                            print('Basic due date after registration extension date. No extension required. Skipping.')
            else:
                print('Assignment missing either a due date (' + str(a.due_at) + ') or unlock date (' + str(a.unlock_at) + '). Not checking.')

        if need_synchronize:
            print('Overrides changed. Deleting out-of-date cache and forcing canvas synchronize...')
            if os.path.exists(self.canvas_cache_filename):
                os.remove(self.canvas_cache_filename)
            self.synchronize_canvas(allow_cache = False)

        print('Done.')
        return 

    def run_workflow(self):
        #apply late registration dates
        self.apply_latereg_extensions(self.config.latereg_extension_days)

        #TODO create subms
        for a in self.assignments:
            if a.due_date

        #TODO update subm due dates
 
        #TODO any assignments past due copy and clone git and generate etc

        #TODO clone git repo into this directory 

        #TODO generate the assignment

        #TODO process subms of active students; pass docker interface to each subm's call, then pass result back to subm?

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

    

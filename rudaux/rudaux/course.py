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
from .docker import Docker
import git
import shutil


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
        self.canvas = Canvas(self.config, self.dry_run)
        self.canvas_cache_filename = os.path.join(self.course_dir, self.config.name + '_canvas_cache.pk')
        self.synchronize_canvas(allow_canvas_cache)
        
        #=======================================================#
        #      Create the JupyterHub Interface                  #
        #=======================================================#

        print('Creating JupyterHub interface...')
        self.jupyterhub = JupyterHub(self.config, self.dry_run)

        #=======================================================#
        #      Create the interface to ZFS                      #
        #=======================================================#

        print('Creating ZFS interface...')
        self.zfs = ZFS(self.config, self.dry_run)

        #=======================================================#
        #      Create the interface to Docker                   #
        #=======================================================#

        print('Creating Docker interface...')
        self.docker = Docker(self.config, self.dry_run)

        
        #=======================================================#
        #      Load the saved state                             #
        #=======================================================#
        print('Loading snapshots...')
        self.snapshots_filename = os.path.join(self.course_dir, self.config.name +'_snapshots.pk')
        self.load_snapshots()
        print('Loading submissions...')
        self.submissions_filename = os.path.join(self.course_dir, self.config.name +'_submissions.pk')
        self.load_submissions()
        
        print('Done.')
       
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
    
    def load_snapshots(self):
        print('Loading the list of taken snapshots...')
        if os.path.exists(self.snapshots_filename):
            with open(self.snapshots_filename, 'rb') as f:
                self.snapshots = pk.load(f)
        else: 
            print('No snapshots file found. Initializing empty list.')
            self.snapshots = []
        return

    def load_submissions(self):
        print('Loading the list of submissions...')
        if os.path.exists(self.submissions_filename):
            with open(self.submissions_filename, 'rb') as f:
                self.submissions = pk.load(f)
        else: 
            print('No submissions file found. Initializing empty dict.')
            self.submissions = {}
        return

    def save_snapshots(self):
        print('Saving the taken snapshots list...')
        if not self.dry_run:
            with open(self.snapshots_filename, 'wb') as f:
                pk.dump(self.snapshots, f)
            print('Done.')
        else:
            print('[Dry Run: snapshot list not saved]')
        return

    def save_submissions(self):
        print('Saving the submissions list...')
        if not self.dry_run:
            with open(self.submissions_filename, 'wb') as f:
                pk.dump(self.submissions, f)
            print('Done.')
        else:
            print('[Dry Run: submissions not saved]')
        return

    def take_snapshots(self):
        print('Taking snapshots')
        for a in self.assignments:
            if a.due_at and a.due_at < plm.now() and a.name not in self.snapshots:
                print('Assignment ' + a.name + ' is past due and no snapshot exists yet. Taking a snapshot [' + a.name + ']')
                try:
                    self.zfs.snapshot_all(a.name)
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
                        self.zfs.snapshot_user(over['student_ids'][0], snapname)
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
        self.save_snapshots()

    def get_due_date(self, a, s):
        basic_date = a.due_at

        #get overrides for the student
        a_s_overrides = [over for over in a.overrides if s.canvas_id in over['student_ids'] and over['due_at']]

        #if there was no override, return the basic date
        if len(a_s_overrides) == 0:
            return basic_date, None

        #if there was one, get the latest override date
        latest_override = a_s_overrides[0]
        for over in a_s_overrides:
            if over['due_at'] > latest_override['due_at']:
                latest_override = over
        
        #return the latest date between the basic and override dates
        if latest_override['due_at'] > basic_date:
            return latest_override['due_at'], latest_override
        else:
            return basic_date, None

    def apply_latereg_extensions(self, extdays):
        need_synchronize = False
        tz = self.course_info['time_zone']
        fmt = 'ddd YYYY-MM-DD HH:mm:ss'
        print('Applying late registration extensions')
        for a in self.assignments:
            if a.due_at and a.unlock_at: #if the assignment has both a due date and unlock date set
                print('Checking ' + str(a.name))
                for s in self.students:
                    regdate = s.reg_updated if s.reg_updated else s.reg_created
                    if s.status == 'active' and regdate > a.unlock_at:
                        #if student s active and registered after assignment a was unlocked
                        print('Student ' + s.name + ' registration date (' + regdate.in_timezone(tz).format(fmt)+') after unlock date of assignment ' + a.name + ' (' + a.unlock_at.in_timezone(tz).format(fmt) + ')')
                        #get their due date w/ no late registration
                        due_date, override = self.get_due_date(a, s)
                        print('Current due date: ' + due_date.in_timezone(tz).format(fmt) + ' from override: ' + str(True if override else False))
                        #the late registration due date
                        latereg_date = regdate.add(days=extdays)
                        print('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt) + ' from override: ' + str(True if override else False))
                        if latereg_date > due_date:
                            print('Creating automatic late registration extension to ' + latereg_date.in_timezone(tz).format(fmt)) 
                            if override:
                                print('Removing old override')
                                self.canvas.remove_override(a.canvas_id, override['id'])
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

        #print('Creating grader folders/accounts for assignments')
        ## make sure each assignment past due has grader folders set up
        #for a in self.assignments:
        #    # for any assignment past due
        #    if a.due_date < plm.now():
        #        # create a user folder and jupyterhub account for each grader if needed
        #        for i in range(self.config.num_graders):
        #            grader_name = a.name+'-grader-'+str(i)
        #            # create the zfs volume and clone the instructor repo
        #            if not self.zfs.user_folder_exists(grader_name):
        #                print('Assignment ' + a.name + ' past due, no ' + grader_name + ' folder created yet. Creating')
        #                self.zfs.create_user_folder(grader_name)
        #            # if the repo doesn't exist, clone it
        #            repo_path = os.path.join(self.config.user_folder_root, grader_name, self.config.instructor_repo_name)
        #            if not os.path.exists(repo_path):
        #                print('Cloning course repository from ' + self.config.instructor_repo_url)
        #                if not self.dry_run:
        #                    try:
        #                        os.mkdir(repo_path)
        #                        git.Repo.clone_from(self.config.instructor_repo_url, repo_path)
        #                    except git.exc.GitCommandError as e:
        #                        print('Error cloning course repository.')
        #                        print(e)
        #                        print('Cleaning up repo path')
        #                        shutil.rmtree(repo_path)
        #                else:
        #                    print('[Dry Run: would have called mkdir('+repo_path+') and git clone ' + self.config.instructor_repo_url + ' into ' + repo_path)
        #            # if the assignment hasn't been generated yet, generate it
        #            generated_asgns = self.docker.run('nbgrader db assignment list', repo_path)
        #            if a.name not in generated_asgns:
        #                print('Assignment not yet generated. Generating')
        #                output = self.docker.run('nbgrader generate_assignment --force ' + a.name, repo_path)
        #           
        #            # if solution not generated yet, generate it
        #            #TODO
        #            
        #            # create the jupyterhub user
        #            if not self.jupyterhub.grader_exists(grader_name):
        #                self.jupyterhub.assign_grader(grader_name, self.config.graders[a.name][i])

        #print('Creating/collecting/cleaning submissions')
        ## create submissions for assignments
        #for a in self.assignments:
        #    if a.due_date < plm.now(): #only process assignments that are past-due
        #        for s in self.students:
        #            #if there isn't a submission for this assignment/student, create one and assign it to a grader
        #            if a.name+'-'+s.canvas_id not in self.submissions:
        #                self.submissions[a.name+'-'+s.canvas_id] = Submission()
        #                assign_it
        #            #update the submission due date from canvas
        #            subm = self.submissions[a.name+'-'+s.canvas_id]
        #            subm.due_date,  = self.get_due_date(a, s)
        #            if due_Date_past:
        #                collect_it
        #                clean_it
        #                schedule_for_autograding
        #                return_soln if succesfful
        
        #TODO run all autograding jobs

        #TODO schedule then run feedback generation 
      
        #TODO post grade
 
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

    

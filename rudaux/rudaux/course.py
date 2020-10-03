import os, sys, pwd
import pickle as pk
import tqdm
import pendulum as plm
import terminaltables as ttbl
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import editdistance
from subprocess import CalledProcessError
from .canvas import Canvas, GradeNotUploadedError
from .jupyterhub import JupyterHub
from .zfs import ZFS
from .person import Person
from .group import Group
from .assignment import Assignment
from .docker import Docker, DockerError
from .submission import Submission, SubmissionStatus, MultipleGraderError
from .notification import SMTP
import git
import shutil
import random
import traceback

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
        self.config.user_folder_root.rstrip('/')
        #TODO make sure the user_folder_root is actually right; we use rm and chown on subdirectories below
        
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
        #      Create the interface to SendMail                 #
        #=======================================================#

        print('Creating Notification interface...')
        self.notifier = self.config.notification_type(self.config, self.dry_run)
        
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

            print('Obtaining/processing group information from Canvas...')
            group_dicts = self.canvas.get_groups()
            self.groups = [Group(gr) for gr in group_dicts]
            print('Done.')
        except Exception as e:
            print('Exception encountered during synchronization')
            print(e)
            print(traceback.format_exc())
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
                    self.groups = canvas_cache['groups']
        else:
            print('Saving canvas cache file...')
            with open(self.canvas_cache_filename, 'wb') as f:
                pk.dump({'course_info' : self.course_info,
                         'students' : self.students,
                         'fake_students' : self.fake_students,
                         'instructors' : self.instructors,
                         'tas' : self.tas,
                         'assignments' : self.assignments,
                         'groups' : self.groups,
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


    #TODO remove load/save submissions? unused I think
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

    #TODO throughout: there is a lot of checking for a.due_at and a.unlock_at -- make sure to have an "else" and print some msg if check fails
    #TODO alternatively, when we synch canvas, only keep assignments with a due&unlock date, and report others as invalid and remove

    #TODO rather than save a list of taken snapshots and update it, detect which snapshots were already taken from zfs list
    def take_snapshots(self):
        print('Taking snapshots')
        for a in self.assignments:
            if (a.due_at is not None) and a.due_at < plm.now() and a.name not in self.snapshots:
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
                snapname = a.name + '-override-' + over['id'] #TODO don't hard code this pattern here since we need it in submission too
                if (over['due_at'] is not None) and over['due_at'] < plm.now() and not (snapname in self.snapshots):
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

    def apply_latereg_extensions(self): 
        need_synchronize = False
        tz = self.course_info['time_zone']
        fmt = 'ddd YYYY-MM-DD HH:mm:ss'
        print('Applying late registration extensions')
        for a in self.assignments:
            print('Checking ' + str(a.name))
            print('Due: ' + str(a.due_at.in_timezone(tz).format(fmt) if a.due_at is not None else a.due_at) + ' Unlock: ' + str(a.unlock_at.in_timezone(tz).format(fmt) if a.unlock_at is not None else a.unlock_at))
            if (a.due_at is not None) and (a.unlock_at is not None): #if the assignment has both a due date and unlock date set
                for s in self.students:
                    regdate = s.reg_updated if (s.reg_updated is not None) else s.reg_created
                    if s.status == 'active' and regdate > a.unlock_at:
                        #if student s active and registered after assignment a was unlocked
                        print('Student ' + s.name + ' registration date (' + regdate.in_timezone(tz).format(fmt)+') after unlock date of assignment ' + a.name + ' (' + a.unlock_at.in_timezone(tz).format(fmt) + ')')
                        #get their due date w/ no late registration
                        due_date, override = a.get_due_date(s)
                        print('Current due date: ' + due_date.in_timezone(tz).format(fmt) + ' from override: ' + str(True if (override is not None) else False))
                        #the late registration due date
                        latereg_date = regdate.add(days=self.config.latereg_extension_days)
                        print('Late registration extension date: ' + latereg_date.in_timezone(tz).format(fmt))
                        if latereg_date > due_date:
                            print('Creating automatic late registration extension to ' + latereg_date.in_timezone(tz).format(fmt)) 
                            if override is not None:
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
                            print('Current due date after registration extension date. No extension required. Skipping.')
            else:
                print('Assignment missing either a due date (' + str(a.due_at) + ') or unlock date (' + str(a.unlock_at) + '). Not checking.')

        #TODO create a "needs_synch" flag instead of doing it now; lazy synch
        #if need_synchronize:
        #    print('Overrides changed. Deleting out-of-date cache and forcing canvas synchronize...')
        #    if os.path.exists(self.canvas_cache_filename):
        #        os.remove(self.canvas_cache_filename)
        #    self.synchronize_canvas(allow_cache = False)

        print('Done.')
        return 


    #TODO what happens if rudaux config doesn't have this one's name?
    def create_grader_folders(self, a):
        print('Creating grader folders/accounts for assignments')
        #TODO don't hardcode 'jupyter' here
        jupyter_uid = pwd.getpwnam('jupyter').pw_uid
        # create a user folder and jupyterhub account for each grader if needed
        print('Checking assignment ' + a.name + ' with grader list ' + str(self.config.graders[a.name]))
        for i in range(len(self.config.graders[a.name])):
            grader_name = a.grader_basename() + str(i)
            print('Checking assignment ' + a.name + ' grader ' + self.config.graders[a.name][i] + '(' +grader_name + ')')

            # create the zfs volume and clone the instructor repo
            print('Checking if grader folder exists..')
            if not self.zfs.user_folder_exists(grader_name):
                print('Assignment ' + a.name + ' past due, no ' + grader_name + ' folder created yet. Creating')
                self.zfs.create_user_folder(grader_name)
            print('Grading folder exists')

            # create the jupyterhub user
            print('Checking if jupyter user ' + grader_name + ' exists')
            if not self.jupyterhub.grader_exists(grader_name):
                print('Grader ' + grader_name + ' not created on the hub yet; assigning ' + self.config.graders[a.name][i])
                self.jupyterhub.assign_grader(grader_name, self.config.graders[a.name][i])   
            else:
                print('User exists!')

            # if not a valid repo with an nbgrader config file, clone it
            repo_path = os.path.join(self.config.user_folder_root, grader_name)
            #TODO if there's an error cloning the repo or an unknown error when doing the initial test repo create
            # email instructor and print a message to tell the user to create a deploy key
            print('Checking if ' + str(repo_path) + ' is a valid course git repository')
            repo_valid = False
            #allow no such path or invalid repo errors; everything else should raise
            try:
                tmprepo = git.Repo(repo_path)
            except git.exc.InvalidGitRepositoryError as e:
                pass
            except git.exc.NoSuchPathError as e:
                pass
            else:
                repo_valid = True
            if not repo_valid:
                print(repo_path + ' is not a valid course repo. Cloning course repository from ' + self.config.instructor_repo_url)
                if not self.dry_run:
                    git.Repo.clone_from(self.config.instructor_repo_url, repo_path)
                    for root, dirs, files in os.walk(repo_path):  
                        for di in dirs:  
                          os.chown(os.path.join(root, di), jupyter_uid, jupyter_uid)
                        for fi in files:
                          os.chown(os.path.join(root, fi), jupyter_uid, jupyter_uid)
                else:
                    print('[Dry Run: would have removed any file/folder at ' + repo_path + ', called mkdir('+repo_path+') and git clone ' + self.config.instructor_repo_url + ' into ' + repo_path)
            else:
                print('Repo valid.')

            # if the assignment hasn't been generated yet, generate it
            print('Checking if assignment ' + a.name + ' has been generated for grader ' + grader_name)
            generated_asgns = self.docker.run('nbgrader db assignment list', repo_path)
            if a.name not in generated_asgns['log']:
                print('Assignment not yet generated. Generating')
                output = self.docker.run('nbgrader generate_assignment --force ' + a.name, repo_path)
                print(output['log'])
                if 'ERROR' in output['log']:
                    raise DockerError('Error generating assignment ' + a.name + ' in grader folder ' + grader_name + ' at repo path ' + repo_path, output['log'])
            else:
                print('Assignment already generated')
           
            # if solution not generated yet, generate it
            local_path = os.path.join('source', a.name, a.name + '.ipynb')
            soln_name = a.name + '_solution.html' 
            print('Checking if solution generated...')
            if not os.path.exists(os.path.join(repo_path, soln_name)):
                print('Solution not generated; generating')
                output = self.docker.run('jupyter nbconvert ' + local_path + ' --output=' + soln_name + ' --output-dir=.', repo_path) 
                print(output['log'])
                if 'ERROR' in output['log']:
                    raise DockerError('Error generating solution for assignment ' + a.name + ' in grader folder ' + grader_name + ' at repo path ' + repo_path, output['log'])
            else:
                print('Solution already generated')

    def process(self, func, submissions, to_process, valid_flags):

        if (valid_flags is not None) and (not isinstance(valid_flags, list)):
            valid_flags = [valid_flags]

        results = {}
        for sid in to_process:
            if valid_flags is None or to_process[sid] in valid_flags:
                results[sid] = func(submissions[sid]) 
        return results

    def grading_workflow(self): 
        
        for asgn in self.assignments:
            #only do stuff for assignments past their basic due date
            if asgn.due_at < plm.now():
                #create grader zfs home folders  / jupyterhub accounts
                #don't continue after this point unless grader creation is successful
                print('Working on assignment ' + asgn.name)
                print('Creating grader folders...')
                create_folder_error = False
                try:
                    self.create_grader_folders(asgn)
                except DockerError as e:
                    error_message = e.message +'\nDocker output:\n' +e.docker_output
                    error_traceback = traceback.format_exc()
                    create_folder_error = True
                except git.exc.GitCommandError as e:
                    error_message = str(e)
                    error_traceback = traceback.format_exc()
                    create_folder_error = True
                except Exception as e:    
                    error_message = str(e)
                    error_traceback = traceback.format_exc()
                    create_folder_error = True

                if create_folder_error:
                    print(f"""
                      Error encountered while creating grader folders for {asgn.name}. Email sent to instructor. Skipping this assignment for now.
                      Message: {error_message}
                      Trace: {error_traceback}
                      """)
                    self.notifier.submit(self.config.instructor_user, 'Action Required: grader folder creation failed for ' + asgn.name+':\r\n' + error_message + '\r\n' + error_traceback)
                    continue

                print('Getting uploaded/posted submissions on canvas')
                canvas_subms = self.canvas.get_submissions(asgn.canvas_id)
                posted_grades = {subm['student_id'] : subm['posted_at'] is not None for subm in canvas_subms} 
                uploaded_grades = {subm['student_id'] : subm['score'] is not None for subm in canvas_subms}

                #create the set of submission objects for any unfinished assignments 
                print('Creating submission objects')
                submissions = {}
                errors = []
                for stu in self.students:
                    try:
                        submissions[stu.canvas_id] = Submission(asgn, stu, uploaded_grades[stu.canvas_id], posted_grades[stu.canvas_id], self.config)
                    except MultipleGraderError as e:
                        print(f'Multiple grader error in creating submission for {asgn.name} : {stu.canvas_id}')
                        print(e.message)
                        submissions.pop(stu.canvas_id, None)
                        errors.append(f'Multiple grader error in creating submission for {asgn.name} : {stu.canvas_id}\r\n'+e.message+'\r\n')
                    except Exception as e:
                        print(f'Error creating submission for {asgn.name} : {stu.canvas_id}')
                        submissions.pop(stu.canvas_id, None)
                        errors.append(f'Error creating submission for {asgn.name} : {stu.canvas_id}\r\n'+e.message+'\r\n')

                if len(errors) > 0:
                    print('Errors creating submissions detected. Notifying instructor and stopping processing this assignment.') 
                    err_msg = 'Errors detected in ' + asgn.name + ' processing. Action required.' + \
        								     '\r\n SUBMISSION CREATION ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors)
                    print(err_msg)
                    self.notifier.submit(self.config.instructor_user, err_msg)
                    continue
                        

                #make sure all submissions are prepared
                print('Preparing submissions')
                prep_results = self.process(lambda subm : Submission.prepare(subm, self.course_info['time_zone']), submissions, submissions, None)

                # check if we can return the solutions to the students yet, and if so return
                print('Checking whether solutions can be returned')
                n_total = len(prep_results)
                n_outstanding = len([p for p in prep_results if prep_results[p] == SubmissionStatus.NOT_DUE])
                retsoln_results = {}
                if (n_total - n_outstanding)/n_total >= self.config.return_solution_threshold: 
                    print('Threshold reached(' + str((n_total - n_outstanding)/n_total) + '>=' + str(self.config.return_solution_threshold)+'); this assignment is returnable')
                    if plm.now() > plm.parse(self.config.earliest_solution_return_date, tz=self.course_info['time_zone']):
                        retsoln_results = self.process(Submission.return_solution, submissions, prep_results, [SubmissionStatus.MISSING, SubmissionStatus.PREPARED])
                    else:
                        print('Earliest return date (' +self.config.earliest_solution_return_date + ') not passed yet. Skipping')
                else:
                    print('Threshold not reached (' + str((n_total - n_outstanding)/n_total) + '<' + str(self.config.return_solution_threshold)+'); this assignment is not yet returnable')
 

                #any missing assignments get a 0
                print('Assigning 0 to all missing submissions')
                miss_results = self.process(lambda subm: Submission.finalize_failed_submission(subm, self.canvas), submissions,
                                               prep_results, SubmissionStatus.MISSING)

                print('Submitting autograding tasks')
                ag_results = self.process(lambda subm : Submission.submit_autograding(subm, self.docker), submissions, 
						prep_results, SubmissionStatus.PREPARED)
                
                print('Running autograding tasks')
                docker_results = self.docker.run_all()
                
                print('Checking grading status')
                gr_results = self.process(lambda subm : Submission.check_grading(subm, self.canvas, docker_results), submissions, 
						ag_results, [SubmissionStatus.NEEDS_AUTOGRADE, SubmissionStatus.AUTOGRADED])

                print('Checking if any errors occurred and submitting error/failure notifications for instructors')
                errors = {'preparing': [sid +':\r\n' + str(submissions[sid].error) for sid in prep_results if prep_results[sid] == SubmissionStatus.ERROR],
                          'returningsolns': [sid +':\r\n' + str(submissions[sid].error) for sid in retsoln_results if retsoln_results[sid] == SubmissionStatus.ERROR],
                          'autograding': [sid +':\r\n' + 'autograding failed previously' for sid in ag_results if ag_results[sid] == SubmissionStatus.AUTOGRADE_FAILED_PREVIOUSLY] + 
                                         [sid +':\r\n' + str(submissions[sid].error) for sid in gr_results if gr_results[sid] == SubmissionStatus.ERROR or gr_results[sid] == SubmissionStatus.AUTOGRADE_FAILED],
                          'uploading':  [sid +':\r\n' + str(submissions[sid].error) for sid in miss_results if miss_results[sid] == SubmissionStatus.ERROR]}
                if any([len(v) > 0 for k, v in errors.items()]):
                    print('Errors detected. Notifying instructor and stopping processing this assignment.') 
                    err_msg = 'Errors detected in ' + asgn.name + ' processing. Action required.' + \
        								     '\r\n PREPARATION ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['preparing']) + \
                                                                             '\r\n RETURN_SOLN ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['returningsolns']) + \
        								     '\r\n AUTOGRADING ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['autograding']) + \
        								     '\r\n UPLOADING ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['uploading'])
                    print(err_msg)
                    self.notifier.submit(self.config.instructor_user, err_msg)
                    continue

                print('Checking if any manual grading needs to happen and submitting notifications for TAs')
                not_done_grading = False
                for grader_ta in list(set(self.config.graders[asgn.name])): #use list(set(...)) in case same account is assigned to multiple grader accounts for some reason
                    #grader_ta = self.config.graders[asgn.name][int(submissions[res].grader.split('-')[-1])]
                    grading_tasks = [submissions[sid].grader + ' -- ' + asgn.name + ' -- ' + submissions[sid].stu.canvas_id for sid in gr_results if gr_results[sid] == SubmissionStatus.NEEDS_MANUAL_GRADE and grader_ta == self.config.graders[asgn.name][int(submissions[sid].grader.split('-')[-1])]]
                    if len(grading_tasks) > 0:
                        print('Grader ' + grader_ta + ' has grading task for ' + asgn.name +'. Pinging if today is an email day.')
                        if plm.now().in_timezone(self.course_info['time_zone']).format('dddd') in self.config.notify_days:
                            self.notifier.submit(grader_ta, 'You have a manual grading task to do for assignment ' + asgn.name +'! \r\n'+('Note: There are still ' + str(n_outstanding) + ' student submissions not due yet due to extensions/late registrations/etc; your task list may be incomplete and more tasks may show up over time.' if n_outstanding > 0 else 'All submissions have been collected, so no additional submissions will be added.') +  '\r\nEach entry below is an assignment that you have to grade, and is listed in the format [grader user account] -- [assignment name] -- [student id]. \r\n To grade the assignments, please sign in to the course JupyterHub with the [grader user account] username and the same password as your personal user account.\r\n'+ 
                                                     '\r\n'.join(grading_tasks))
                        not_done_grading = True

                if not_done_grading:
                    print('Not done grading this assignment. Waiting until grading is complete before moving on')
                    continue

                print('Grading complete.')

                print('Uploading grades')
                ul_results = self.process(lambda subm : Submission.upload_grade(subm, self.canvas), submissions, 
						gr_results, SubmissionStatus.DONE_GRADING)

                print('Submitting feedback generation tasks')
                fb_results = self.process(lambda subm : Submission.submit_genfeedback(subm, self.docker), submissions, 
						ul_results, SubmissionStatus.GRADE_UPLOADED)

                print('Running feedback generation tasks')
                docker_results = self.docker.run_all()

                print('Checking feedback gen status')
                fbc_results = self.process(lambda subm : Submission.check_feedback(subm, docker_results), submissions, 
						fb_results, [SubmissionStatus.NEEDS_FEEDBACK, SubmissionStatus.FEEDBACK_GENERATED])

                print('Checking if any errors occurred and submitting error/failure notifications for instructors')
                errors = {'uploading':  [sid +':\r\n' + str(submissions[sid].error) for sid in ul_results if ul_results[sid] == SubmissionStatus.ERROR],
                          'feedback': [sid +':\r\n' + 'feedback generation failed previously' for sid in fb_results if fb_results[sid] == SubmissionStatus.FEEDBACK_FAILED_PREVIOUSLY] + 
                                         [sid +':\r\n' + str(submissions[sid].error) for sid in fbc_results if fbc_results[sid] == SubmissionStatus.ERROR or fbc_results[sid] == SubmissionStatus.FEEDBACK_FAILED]
                          }
                if any([len(v) > 0 for k, v in errors.items()]):
                    print('Errors detected. Notifying instructor and stopping processing this assignment.') 
                    err_msg = 'Errors detected in ' + asgn.name + ' processing. Action required.' + \
        								     '\r\n GRADE UPLOAD ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['uploading']) + \
        								     '\r\n FEEDBACK ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['feedback'])
                    print(err_msg)
                    self.notifier.submit(self.config.instructor_user, err_msg)
                    continue

                print('Checking whether feedback can be returned')
                n_total = len(prep_results)
                n_outstanding = len([p for p in prep_results if prep_results[p] == SubmissionStatus.NOT_DUE])
                retfdbk_results = {}
                if (n_total - n_outstanding)/n_total >= self.config.return_solution_threshold: 
                    print('Threshold reached(' + str((n_total - n_outstanding)/n_total) + '>=' + str(self.config.return_solution_threshold)+'); this assignment is returnable')
                    if plm.now() > plm.parse(self.config.earliest_solution_return_date, tz=self.course_info['time_zone']):
                        retfdbk_results = self.process(Submission.return_feedback, submissions, {key : val for (key, val) in fbc_results.items() if posted_grades[key]}, SubmissionStatus.FEEDBACK_GENERATED)
                    else:
                        print('Earliest return date (' +self.config.earliest_solution_return_date + ') not passed yet. Skipping')
                    
                else:
                    print('Threshold not reached (' + str((n_total - n_outstanding)/n_total) + '<' + str(self.config.return_solution_threshold)+'); this assignment is not yet returnable')

                errors = {'retfeedback':  [sid +':\r\n' + str(submissions[sid].error) for sid in retfdbk_results if retfdbk_results[sid] == SubmissionStatus.ERROR]}
                if any([len(v) > 0 for k, v in errors.items()]):
                    print('Errors detected. Notifying instructor and stopping processing this assignment.') 
                    err_msg = 'Errors detected in ' + asgn.name + ' processing. Action required.' + \
        								     '\r\n FEEDBACK RETURN ERRORS:\r\n' + \
                                                                             '\r\n'.join(errors['retfeedback'])
                    print(err_msg)
                    self.notifier.submit(self.config.instructor_user, err_msg)
                    continue 
               
                #check if all grades are posted
                print('Checking if all grades have been posted...')
                if all([submissions[subm].grade_posted for subm in submissions]):
                    print('All grades posted.')
                elif any([submissions[subm].grade_uploaded and not submissions[subm].grade_posted  for subm in submissions]):
                    print('There are unposted grades. Pinging instructor to post if today is an email day.')
                    if plm.now().in_timezone(self.course_info['time_zone']).format('dddd') in self.config.notify_days:
                        self.notifier.submit(self.config.instructor_user, 'Action Required: Post grades for assignment ' + asgn.name)
                else:
                    print('No unposted / uploaded grades, but not all grades posted yet. Waiting.')
                  
                #if asgn past due end
            # loop over assignments end
        # func base indentation
        print('Sending notifications')
        self.send_notifications()
        return
 
    def send_notifications(self):
        self.notifier.connect()
        self.notifier.notify_all()
        self.notifier.close()

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

    

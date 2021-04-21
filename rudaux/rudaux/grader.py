import pendulum as plm
import prefect
from prefect import task
from prefect.engine import signals
import os
from subprocess import check_output, STDOUT
from dictauth.users import add_user, remove_user, get_users
from collections import namedtuple
import git
import shutil
from .docker import _run_docker

class GradingStatus(IntEnum):
    ASSIGNED = 0
    NOT_DUE = 1
    MISSING = 2
    COLLECTED = 3
    PREPARED = 4
    NEEDS_AUTOGRADE = 5
    AUTOGRADED = 6
    AUTOGRADE_FAILED_PREVIOUSLY = 7
    AUTOGRADE_FAILED = 8
    NEEDS_MANUAL_GRADE = 9
    DONE_GRADING = 10
    GRADE_UPLOADED = 11
    NEEDS_FEEDBACK = 12
    FEEDBACK_GENERATED = 13
    FEEDBACK_FAILED_PREVIOUSLY = 14
    FEEDBACK_FAILED = 15
    NEEDS_POST = 16
    DONE = 17

def _recursive_chown(path, uid):
    for root, dirs, files in os.walk(path):  
        for di in dirs:  
          os.chown(os.path.join(root, di), uid, uid) 
        for fi in files:
          os.chown(os.path.join(root, fi), uid, uid)

def _clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())

def _grader_account_name(assignment, ta):
    return _clean_jhub_uname(assignment['name'])+'-'+_clean_jhub_uname(ta)

@task
def validate_config(config):
    #config.graders
    #config.snapshot_window
    #config.grading_jupyter_user
    #config.grading_dataset_root
    #config.grading_user_quota
    #config.grading_local_collection_folder

    #config.grading_attached_student_dataset_root
    #config.grading_zfs_path
    #config.grading_jupyterhub_config_dir
    #config.instructor_repo_url
    #config.grading_docker_image
    #config.grading_docker_memory
    #config.grading_docker_bind_folder
    #config.return_solution_threshold
    #config.earliest_solution_return_date
    return config

@task
def build_graders(config, course_info, assignment):
    logger = prefect.context.get("logger")
    logger.info("Checking whether to create graders for assignment {assignment['name']}")
    # check if assignment should be skipped
    if assignment['due_at'] < course_info['start_at']:
        raise signals.FAIL(f"Assignment {assignment['name']} due date {assignment['due_at']} is before the course start date ({course_info['start_at']}). This can happen when courses are copied from past semesters. Please make sure all assignment unlock/due dates are updated for the present semester.")

    if assignment['due_at'] > plm.now():
        logger.info(f"Assignment {assignment['name']} due date {assignment['due_at']} is in the future. Skipping.")
        return []

    logger.info("Creating graders...")
    graders = []
    for i in range(len(config.graders[assignment['name']])):
        ta = config.graders[assignment['name']][i]
        grader_name = _grader_account_name(assignment, ta)
        logger.info(f'Building grader account {grader_name}')
        # ensure TA user exists
        logger.info(f"Checking if jupyterhub user {ta} exists")
        Args = namedtuple('Args', 'directory')
        args = Args(directory = config.grading_jupyterhub_config_dir)
        output = get_users(args)
        if ta not in output:
            raise signals.FAIL(f"User {ta} does not exist! Make sure to use dictauth to create a grader account for each of the TAs listed in config.graders")
        else:
            logger.info(f"User {ta} exists.")
        grader = {}
        grader['assignment'] = assignment
        grader['ta'] = ta
        grader['name'] = grader_name
        grader['index'] = i
        grader['unix_uid'] = pwd.getpwnam(config.grading_jupyter_user).pw_uid
        grader['unix_quota'] = config.grading_user_quota
        grader['folder'] = os.path.join(config.grading_dataset_root, grader_name).rstrip('/')
        grader['local_source_path'] = os.path.join('source', assignment['name'], assignment['name']+'.ipynb')
        grader['submissions_folder'] = os.path.join(grader['folder'], config.grading_local_collection_folder)
        grader['soln_name'] = assignment['name'] + '_solution.html'
        grader['soln_path'] = os.path.join(grader['folder'], grader['soln_name'])
        graders.append(grader)

    # each grader needs to know what other folders to look in when deciding whether to grade an assignment
    team_subm_folders = [grader['submissions_folder'] for grader in graders]
    for grader in graders:
        grader['team_submissions_folders'] = team_subm_folders

    return graders

@task
def initialize_volume(config, grader):
    logger = prefect.context.get("logger")

    logger.info("Creating volume for grader {grader['name']}")

    # create the zfs volume 
    logger.info('Checking if grader folder exists..')
    if not os.path.exists(grader['folder']):
        logger.info("Folder doesn't exist, creating...")
        check_output([config.grading_zfs_path, 'create', "-o", "refquota="+grader['unix_quota'], grader['folder'].lstrip('/')], stderr=STDOUT)
        _recursive_chown(grader_path, grader['unix_uid'])
    else:
        logger.info("Folder exists.")

    # clone the git repository
    #TODO if there's an error cloning the repo or an unknown error when doing the initial test repo create
    # email instructor and print a message to tell the user to create a deploy key
    logger.info(f"Checking if {grader['folder']} is a valid course git repository")
    repo_valid = False
    #allow no such path or invalid repo errors; everything else should raise
    try:
        tmprepo = git.Repo(grader['folder'])
    except git.exc.InvalidGitRepositoryError as e:
        pass
    except git.exc.NoSuchPathError as e:
        pass
    else:
        repo_valid = True
    if not repo_valid:
        logger.info(f"{grader['folder']} is not a valid course repo. Cloning course repository from {config.instructor_repo_url}")
        git.Repo.clone_from(config.instructor_repo_url, grader['folder'])
        _recursive_chown(grader['folder'], grader['unix_uid'])
    else:
        logger.info(f"{grader['folder']} is a valid course repo.")

    # create the submissions folder
    if not os.path.exists(grader['submissions_folder']):
        os.makedirs(grader['submissions_folder'], exist_ok=True)
        _recursive_chown(grader['submissions_folder'], grader['unix_uid'])

    # if the assignment hasn't been generated yet, generate it
    logger.info(f"Checking if assignment {assignment['name']} has been generated for grader {grader}")
    generated_asgns = run_container(config, 'nbgrader db assignment list', grader['folder'])
    if assignment['name'] not in generated_asgns['log']:
        logger.info(f"Assignment {assignment['name']} not yet generated for grader {grader}")
        output = run_container(config, 'nbgrader generate_assignment --force '+assignment['name'], grader['folder'])
        logger.info(output['log'])
        if 'ERROR' in output['log']:
            raise signals.FAIL(f"Error generating assignment {assignment['name']} for grader {grader['name']} at path {grader['folder']}")
    else:
        logger.info(f"Assignment {assignment['name']} already generated")

    # if the solution hasn't been generated yet, generate it
    logger.info(f"Checking if solution for {assignment['name']} has been generated for grader {grader['name']}")
    if not os.path.exists(grader['soln_path']):
        logger.info(f"Solution for {assignment['name']} not yet generated for grader {grader['name']}")
        output = run_container(config, 'jupyter nbconvert ' + grader['local_source_path'] + ' --output=' + grader['soln_name'] + ' --output-dir=.', grader['folder'])
        logger.info(output['log'])
        if 'ERROR' in output['log']:
            raise signals.FAIL(f"Error generating solution for {assignment['name']} for grader {grader['name']} at path {grader['folder']}")
    else:
        logger.info(f"Solution for {assignment['name']} already generated")

    return grader

@task
def initialize_account(config, grader):
    # create the jupyterhub user
    logger.info(f"Checking if jupyterhub user {grader['name']} exists")
    Args = namedtuple('Args', 'directory')
    args = Args(directory = config.grading_jupyterhub_config_dir)
    output = get_users(args)
    if grader['name'] not in output:
        logger.info(f"User {grader['name']} does not exist; creating")
        Args = namedtuple('Args', 'username directory copy_creds salt digest')
        args = Args(username = grader['name'],
                    directory = config.grading_jupyterhub_config_dir, 
                    copy_creds = grader['ta'],
                    salt = None, 
                    digest = None)
        add_user(args)
        check_call(['systemctl', 'stop', 'jupyterhub'])
        check_call(['systemctl', 'start', 'jupyterhub'])
    else:
        logger.info(f"User {grader} exists.")
    return grader

@task
def assign_grading_tasks(config, grader, submissions):
    tasks = []
    asgn_subms = [subm for subm in submissions if subm['assignment']['id'] == grader['assignment']['id']]

    assigned = False
    for i in range(len(asgn_subms)):
        # search for this student in the grader folders 
        found = False
        for fldr in grader['team_submissions_folders']:
            collected_assignment_path = os.path.join(fldr, asgn_subms[i]['student']['id'], asgn_subms[i]['assignment']['name'] + '.ipynb')
            if os.path.exists(collected_assignment_path):
                found = True
                if fldr == grader['submissions_folder']:
                    assigned = True
                break
        # if not assigned to anyone, and the modulus of the student's index is the current grader, assign here
        if not found and (i % len(grader['team_submissions_folders'])) == grader['index']:
            # assign to this grader
            assigned = True

        # if assigned, create a grading task
        if assigned:
            task = {}
            task['grader'] = grader
            task['submission'] = asgn_subms[i]
            task['collected_assignment_path'] = os.path.join(grader['submissions_folder'], asgn_subms[i]['student']['id'], asgn_subms[i]['assignment']['name'] + '.ipynb')
            task['status'] = GradingStatus.ASSIGNED
            task['grade_to_upload'] = None
            tasks.append(task)

    return tasks

@task
def collect_submission(config, grading_task):
    logger = prefect.context.get("logger")
    if grading_task['submission']['due_at'] < plm.now():
        logger.info(f"Submission ({grading_task['grader']['name'], grading_task['submission']['student']['name']}) is due. Collecting...")
        if not os.path.exists(grading_task['collected_assignment_path']):
            if not os.path.exists(grading_task['submission']['snapped_assignment_path']):
                logger.info(f"Submission missing. Not collecting.")
                grading_task['status'] = GradingStatus.MISSING
                grading_task['score'] = 0.
            else:
                shutil.copy(grading_task['submission']['snapped_assignment_path'], grading_task['collected_assignment_path'])
                os.chown(grading_task['collected_assignment_path'], grading_task['grader']['unix_uid'], grading_task['grader']['unix_uid'])
                grading_task['status'] = GradingStatus.COLLECTED
                logger.info("Submission collected.")
        else:
            logger.info("Submission already collected.")
            grading_task['status'] = GradingStatus.COLLECTED
    else:
        grading_task['status'] = GradingStatus.NOT_DUE
    return grading_task

@task
def handle_missing(config, grading_task):
    logger.info(f"Submission for grading task ({grading_task['grader']['name'], grading_task['submission']['student']['name']}) is missing. Uploading 0 for this assignment and skipping the remainder of this task's flow.")
    try:
        canvas.put_grade(self.asgn.canvas_id, self.stu.canvas_id, pct)
    except GradeNotUploadedError as e: 
        print('Error when uploading grade')
        print(e.message)
        self.error = e
        return SubmissionStatus.ERROR
    self.grade_uploaded = True
    return SubmissionStatus.GRADE_UPLOADED

@task
def clean_submission(config, grading_task):
    logger = prefect.context.get("logger")

    #need to check for duplicate cell ids, see
    #https://github.com/jupyter/nbgrader/issues/1083
    #open the student's notebook
    f = open(grading_task['collected_assignment_path'], 'r')
    nb = json.load(f)
    f.close()
    
    #go through and delete the nbgrader metadata from any duplicated cells
    cell_ids = set()
    for cell in nb['cells']:
      try:
        cell_id = cell['metadata']['nbgrader']['grade_id']
      except:
        continue
      if cell_id in cell_ids:
        logger.info(f"Student {student['name']} assignment {assignment['name']} grader {grader} had a duplicate cell! ID = {cell_id}")
        logger.info("Removing the nbgrader metainfo from that cell to avoid bugs in autograde")
        cell['metadata'].pop('nbgrader', None)
      else:
        cell_ids.add(cell_id)
    
    #write the sanitized notebook back to the submitted folder
    f = open(grading_task['collected_assignment_path'], 'w')
    json.dump(nb, f)
    f.close()

    return grading_task

@task
def get_returnable_solutions(config, course_info, grading_tasks):
    assignment_totals = {}
    assignment_outstanding = {}
    assignment_fracs = {}
    for gt in grading_tasks:
        assignment = gt['submission']['assignment'] 
        anm = assignment['name']
        if anm not in assignment_totals:
            assignment_totals[anm] = 0
        if anm not in assignment_outstanding:
            assignment_outstanding[anm] = 0
        
        assignment_totals[anm] += 1
        if gt['submission']['due_at'] > plm.now():
            assignment_outstanding[anm] += 1

    for k, v in assignment_totals.items():
        assignment_fracs[k] = (v - assignment_outstanding[k])/v

    returnables = []
    for gt in grading_tasks:
        assignment = gt['submission']['assignment'] 
        anm = assignment['name']
        if assignment_fracs[anm] > config.return_solution_threshold and plm.now() > plm.parse(config.earliest_solution_return_date, tz=course_info['time_zone']):
            returnables.append(subm)

    return returnables

@task
def return_solution(config, grading_task):
    logger = prefect.context.get("logger")

    logger.info(f"Returning solution for submission {grading_task['submission']['assignment']['name']}, {grading_task['submission']['student']['name']}")
    if not os.path.exists(grading_task['submission']['soln_path']):
        if os.path.exists(grading_task['submission']['attached_folder']):
            try:
                shutil.copy(grading_task['grader']['soln_path'], grading_task['submission']['soln_path']) 
                os.chown(grading_task['submission']['soln_path'], grading_task['grader']['unix_uid'], grading_task['grader']['unix_uid'])
            except Exception as e:
                raise signals.FAIL(str(e))
        else:
            logger.warning(f"Warning: student folder {grading_task['submission']['attached_folder']} doesnt exist. Skipping solution return.")


# TODO raw code from before, not ported over yet
def upload_grade(self, canvas, failed = False):

    if self.grade_uploaded:
        print('Grade already uploaded. Returning')
        return SubmissionStatus.GRADE_UPLOADED

    print('Uploading grade for submission ' + self.asgn.name+':'+self.stu.canvas_id)
    if failed:
        score = 0
    else:
        try:
            gb = Gradebook('sqlite:///'+self.grader_repo_path +'/gradebook.db')
            subm = gb.find_submission(self.asgn.name, self.student_prefix+self.stu.canvas_id)
            score = subm.score
        except Exception as e:
            print('Error when accessing grade from gradebook db')
            print(e)
            self.error = e
            return SubmissionStatus.ERROR
        finally:
            gb.close()

    try:
        max_score = self.compute_max_score()
    except Exception as e:
        print('Error when trying to compute max score from release notebook')
        print(e)
        self.error = e
        return SubmissionStatus.ERROR

    self.score = score
    self.max_score = max_score
    pct = "{:.2f}".format(100*score/max_score)

    print('Student ' + self.stu.canvas_id + ' assignment ' + self.asgn.name + ' score: ' + str(score) + (' [HARDFAIL]' if failed else ''))
    print('Assignment ' + self.asgn.name + ' max score: ' + str(max_score))
    print('Pct Score: ' + pct)
    print('Posting to canvas...')
    try:
        canvas.put_grade(self.asgn.canvas_id, self.stu.canvas_id, pct)
    except GradeNotUploadedError as e: 
        print('Error when uploading grade')
        print(e.message)
        self.error = e
        return SubmissionStatus.ERROR
    self.grade_uploaded = True
    return SubmissionStatus.GRADE_UPLOADED

# TODO do this when creating the grading task
def compute_max_score(self):
  #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
  #let's compute the max_score from the notebook manually then....
  release_nb_path = os.path.join(self.grader_repo_path, 'release', self.asgn.name, self.asgn.name+'.ipynb')
  f = open(release_nb_path, 'r')
  parsed_json = json.load(f)
  f.close()
  pts = 0
  for cell in parsed_json['cells']:
    try:
      pts += cell['metadata']['nbgrader']['points']
    except Exception as e:
      #will throw exception if cells dont exist / not right type -- that's fine, it'll happen a lot.
      pass
  return pts

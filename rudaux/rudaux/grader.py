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
def build_grading_team(config, assignment):
    logger = prefect.context.get("logger")
    logger.info(f"Initializing grading team for assignment {assignment['name']}")

    logger.info("Validating assignment dates / TA user accounts")
    # fail if assignment has an invalid due/unlock date
    if assignment['unlock_at'] is None or assignment['due_at'] is None:
         sig = signals.FAIL(f"Invalid unlock ({assignment['unlock_at']}) and/or due ({assignment['due_at']}) date for assignment {assignment['name']}")
         sig.assignment = assignment
         raise sig
    if assignment['unlock_at'] < course_info['start_at'] or assignment['due_at'] < course_info['start_at']:
        sig = signals.FAIL(f"Assignment {assignment['name']} due date {assignment['due_at']} and/or unlock date {assignment['unlock_at']} is before the course start date ({course_info['start_at']}). This can happen when courses are copied from past semesters. Please make sure all assignment unlock/due dates are updated for the present semester.")
        sig.assignment = assignment
        raise sig

    # skip the assignment if it isn't due yet
    if assignment['due_at'] > plm.now():
        raise signals.SKIP(f"Assignment {assignment['name']} due date {assignment['due_at']} is in the future. Skipping.")

    graders = []
    for i in range(len(config.graders[assignment['name']])):
        ta = config.graders[assignment['name']][i]
        # ensure TA user exists
        Args = namedtuple('Args', 'directory')
        args = Args(directory = config.grading_jupyterhub_config_dir)
        output = get_users(args)
        if ta not in output:
            raise signals.FAIL(f"Grader account {ta} does not exist! Make sure to use dictauth to create a grader account for each of the TAs listed in config.graders")
        grader = {}
        # initialize any values in the grader that are *not* potential failure points here
        grader['assignment'] = assignment
        grader['ta'] = ta
        grader['name'] = _grader_account_name(assignment, ta)
        grader['index'] = i
        grader['unix_uid'] = pwd.getpwnam(config.grading_jupyter_user).pw_uid
        grader['unix_quota'] = config.grading_user_quota
        grader['folder'] = os.path.join(config.grading_dataset_root, grader['name']).rstrip('/')
        grader['local_source_path'] = os.path.join('source', assignment['name'], assignment['name']+'.ipynb')
        grader['submissions_folder'] = os.path.join(grader['folder'], config.grading_submissions_folder)
        grader['autograded_folder'] = os.path.join(grader['folder'], config.grading_autograded_folder)
        grader['feedback_folder'] = os.path.join(grader['folder'], config.grading_feedback_folder)
        grader['workload'] = len([f for f in os.listdir(grader['submissions_folder']) if os.path.isdir(f)])
        grader['soln_name'] = assignment['name'] + '_solution.html'
        grader['soln_path'] = os.path.join(grader['folder'], grader['soln_name'])
        graders.append(grader)

    return graders

@task
def initialize_volumes(config, graders):
    logger = prefect.context.get("logger")
    for grader in graders:
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

    return graders

@task
def initialize_accounts(config, graders):
    logger = prefect.context.get("logger")
    for grader in graders:
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
    return graders

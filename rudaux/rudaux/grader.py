import pendulum as plm
import pwd
import prefect
from prefect import task
from prefect.engine import signals
import os
from subprocess import check_output, STDOUT
from dictauth.users import add_user, remove_user, get_users
from collections import namedtuple
import git
import shutil
#from .docker import _run_docker

def _recursive_chown(path, uid):
    for root, dirs, files in os.walk(path):
        for di in dirs:
          os.chown(os.path.join(root, di), uid, uid)
        for fi in files:
          os.chown(os.path.join(root, fi), uid, uid)

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

def _clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())

def _grader_account_name(assignment_name, user):
    return _clean_jhub_uname(assignment_name)+'-'+_clean_jhub_uname(user)

def generate_build_grading_team_name(subm_set, **kwargs):
    return 'build-grdteam-'+subm_set['__name__']

@task(checkpoint=False,task_run_name=generate_build_grading_team_name)
def build_grading_team(config, course_group, subm_set):
    logger = prefect.context.get("logger")
    # start by checking whether any of the assignment deadlines are in the future. If so, skip
    for course_name in subm_set:
        if course_name == '__name__':
            continue
        assignment = subm_set[course_name]['assignment']
    
        # skip the assignment if it isn't due yet
        if assignment['due_at'] > plm.now():
            raise signals.SKIP(f"Assignment {assignment['name']} due date {assignment['due_at']} is in the future. Skipping.")

    asgn_name = subm_set['__name__']

    logger.info(f"Initializing grading team for assignment {asgn_name}")
    graders = []
    dictauth_users = config.assignments[course_group][asgn_name]
    for user in dictauth_users:
        # ensure user exists
        Args = namedtuple('Args', 'directory')
        args = Args(directory = config.jupyterhub_config_dir)
        output = get_users(args)
        if user not in output:
            raise signals.FAIL(f"Dictauth user account {user} does not exist! Make sure to use dictauth to create a grader account for each of the TA/instructorss listed in config.assignments")
        grader = {}
        # initialize any values in the grader that are *not* potential failure points here
        grader['user'] = user
        grader['assignment_name'] = asgn_name
        grader['name'] = _grader_account_name(asgn_name,user)
        grader['unix_uid'] = pwd.getpwnam(config.jupyter_user).pw_uid
        grader['unix_quota'] = config.user_quota
        grader['folder'] = os.path.join(config.user_root, grader['name']).rstrip('/')
        grader['local_source_path'] = os.path.join('source', asgn_name, asgn_name+'.ipynb')
        grader['submissions_folder'] = os.path.join(grader['folder'], config.submissions_folder)
        grader['autograded_folder'] = os.path.join(grader['folder'], config.autograded_folder)
        grader['feedback_folder'] = os.path.join(grader['folder'], config.feedback_folder)
        grader['workload'] = len([f for f in os.listdir(grader['submissions_folder']) if os.path.isdir(f)])
        grader['soln_name'] = asgn_name + '_solution.html'
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
            check_output([config.zfs_path, 'create', "-o", "refquota="+grader['unix_quota'], grader['folder'].lstrip('/')], stderr=STDOUT)
            _recursive_chown(grader['folder'], grader['unix_uid'])
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

        aname = grader['assignment_name']

        # if the assignment hasn't been generated yet, generate it
        logger.info(f"Checking if assignment {aname} has been generated for grader {grader}")
        generated_asgns = run_container(config, 'nbgrader db assignment list', grader['folder'])
        if aname not in generated_asgns['log']:
            logger.info(f"Assignment {aname} not yet generated for grader {grader}")
            output = run_container(config, 'nbgrader generate_assignment --force '+aname, grader['folder'])
            logger.info(output['log'])
            if 'ERROR' in output['log']:
                raise signals.FAIL(f"Error generating assignment {aname} for grader {grader['name']} at path {grader['folder']}")
        else:
            logger.info(f"Assignment {aname} already generated")

        # if the solution hasn't been generated yet, generate it
        logger.info(f"Checking if solution for {aname} has been generated for grader {grader['name']}")
        if not os.path.exists(grader['soln_path']):
            logger.info(f"Solution for {aname} not yet generated for grader {grader['name']}")
            output = run_container(config, 'jupyter nbconvert ' + grader['local_source_path'] + ' --output=' + grader['soln_name'] + ' --output-dir=.', grader['folder'])
            logger.info(output['log'])
            if 'ERROR' in output['log']:
                raise signals.FAIL(f"Error generating solution for {aname} for grader {grader['name']} at path {grader['folder']}")
        else:
            logger.info(f"Solution for {aname} already generated")

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
                        directory = config.jupyterhub_config_dir,
                        copy_creds = grader['user'],
                        salt = None,
                        digest = None)
            add_user(args)
            check_call(['systemctl', 'stop', 'jupyterhub'])
            check_call(['systemctl', 'start', 'jupyterhub'])
        else:
            logger.info(f"User {grader['name']} exists.")
    return graders

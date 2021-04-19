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
from ..util import _run_docker
def _recursive_chown(path, uid):
    for root, dirs, files in os.walk(path):  
        for di in dirs:  
          os.chown(os.path.join(root, di), uid, uid) 
        for fi in files:
          os.chown(os.path.join(root, fi), uid, uid)

def _clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())

@task
def validate_config(config):
    #config.graders
    #config.grading_jupyter_user
    #config.grading_dataset_root
    #config.grading_zfs_path
    #config.grading_user_quota
    #config.grading_jupyterhub_config_dir
    #config.instructor_repo_url
    #config.grading_docker_image
    #config.grading_docker_memory
    #config.grading_docker_bind_folder
    return config

@task
def get_grader_assignment_pairs(config, assignments):
    return [(grd, _clean_jhub_uname(asgn['name'])+'-'+_clean_jhub_uname(grd), asgn) for grd in config.graders[asgn['name']] for asgn in assignments]

#TODO what happens if rudaux config doesn't have this one's name?
@task
def initialize_grader(config, grd_pair):
    logger = prefect.context.get("logger")

    ta_user, grader, assignment = grd_pair

    # check if assignment should be skipped
    if assignment['due_at'] >= plm.now():
        raise signals.SKIP(f"Assignment {assignment['name']} due date {assignment['due_at']} in the future. Skipping grader account creation.")
    else:
        logger.info(f"Assignment {assignment['name']} due date {assignment['due_at']} in the past. Initializing grader account {grader}")

    # get the UID for the jupyterhub unix user account (for folder permissions/ownership etc)
    jupyter_uid = pwd.getpwnam(config.grading_jupyter_user).pw_uid
    logger.info(f"Jupyter user {config.grading_jupyter_user} has UID {jupyter_uid}")

    # create the zfs volume 
    logger.info('Checking if grader folder exists..')
    grader_path = os.path.join(config.jupyter_user_folder, grader).rstrip('/')
    if not os.path.exists(grader_path): 
        logger.info("Folder doesn't exist, creating...")
        check_output([config.grading_zfs_path, 'create', "-o", "refquota="+config.grading_user_quota, grader_path.lstrip('/')], stderr=STDOUT)
        _recursive_chown(grader_path, jupyter_uid)
    else:
        logger.info("Folder exists.")

    # create the jupyterhub user
    logger.info(f"Checking if jupyterhub user {grader} exists")
    Args = namedtuple('Args', 'directory')
    args = Args(directory = config.grading_jupyterhub_config_dir)
    output = get_users(args)
    if grader not in output:
        logger.info(f"User {grader} does not exist; creating")
        Args = namedtuple('Args', 'username directory copy_creds salt digest')
        args = Args(username = grader_name, 
                    directory = config.grading_jupyterhub_config_dir, 
                    copy_creds = ta_user, 
                    salt = None, 
                    digest = None)
        add_user(args)
        check_call(['systemctl', 'stop', 'jupyterhub'])
        check_call(['systemctl', 'start', 'jupyterhub'])
    else:
        logger.info(f"User {grader} exists.")
       
    # clone the git repository
    #TODO if there's an error cloning the repo or an unknown error when doing the initial test repo create
    # email instructor and print a message to tell the user to create a deploy key
    logger.info(f"Checking if {grader_path} is a valid course git repository")
    repo_valid = False
    #allow no such path or invalid repo errors; everything else should raise
    try:
        tmprepo = git.Repo(grader_path)
    except git.exc.InvalidGitRepositoryError as e:
        pass
    except git.exc.NoSuchPathError as e:
        pass
    else:
        repo_valid = True
    if not repo_valid:
        logger.info(f"{grader_path} is not a valid course repo. Cloning course repository from {config.instructor_repo_url}")
        git.Repo.clone_from(self.config.instructor_repo_url, grader_path)
        _recursive_chown(grader_path, jupyter_uid)
    else:
        logger.info(f"{grader_path} is a valid course repo.")

    # if the assignment hasn't been generated yet, generate it
    logger.info(f"Checking if assignment {assignment['name']} has been generated for grader {grader}")
    generated_asgns = _run_docker(config, 'nbgrader db assignment list', grader_path)
    if assignment['name'] not in generated_asgns['log']:
        logger.info(f"Assignment {assignment['name']} not yet generated for grader {grader}")
        output = _run_docker(config, 'nbgrader generate_assignment --force '+assignment['name'], grader_path)
        logger.info(output['log'])
        if 'ERROR' in output['log']:
            raise signals.FAIL(f"Error generating assignment {assignment['name']} for grader {grader} at path {grader_path}")
    else:
        logger.info(f"Assignment {assignment['name']} already generated")

    # if the solution hasn't been generated yet, generate it
    logger.info(f"Checking if solution for {assignment['name']} has been generated for grader {grader}")
    local_path = os.path.join('source', assignment['name'], assignment['name']+'.ipynb')
    soln_name = assignment['name']+'_solution.html'
    if not os.path.exists(os.path.join(grader_path, soln_name)):
        logger.info(f"Solution for {assignment['name']} not yet generated for grader {grader}")
        output = _run_docker(config, 'jupyter nbconvert ' + local_path + ' --output=' + soln_name + ' --output-dir=.', grader_path)
        logger.info(output['log'])
        if 'ERROR' in output['log']:
            raise signals.FAIL(f"Error generating solution for {assignment['name']} for grader {grader} at path {grader_path}")
    else:
        logger.info(f"Solution for {assignment['name']} already generated")


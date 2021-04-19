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

def _grader_account_name(asgn, grd):
    return _clean_jhub_uname(asgn)+'-'+_clean_jhub_uname(grd)

# TODO this is copied from autoext.latereg. Shouldn't duplicate code. Need to think of a better way to structure things. For now, just copy.
def _get_due_date(assignment, student):
    basic_date = assignment['due_at']

    #get overrides for the student
    overrides = [over for over in assignment['overrides'] if student['id'] in over['student_ids'] and (over['due_at'] is not None)]

    #if there was no override, return the basic date
    if len(overrides) == 0:
        return basic_date, None

    #if there was one, get the latest override date
    latest_override = overrides[0]
    for over in overrides:
        if over['due_at'] > latest_override['due_at']:
            latest_override = over
    
    #return the latest date between the basic and override dates
    if latest_override['due_at'] > basic_date:
        return latest_override['due_at'], latest_override
    else:
        return basic_date, None



@task
def validate_config(config):
    #config.graders
    #config.grading_jupyter_user
    #config.grading_dataset_root
    #config.grading_attached_student_dataset_root
    #config.grading_zfs_path
    #config.grading_user_quota
    #config.grading_jupyterhub_config_dir
    #config.instructor_repo_url
    #config.grading_docker_image
    #config.grading_docker_memory
    #config.grading_docker_bind_folder
    #config.grading_local_collection_folder
    #config.return_solution_threshold
    #config.earliest_solution_return_date
    return config

@task
def get_grader_assignment_tuples(config, assignments):
    return [(grd, _grader_account_name(asgn['name'], grd), asgn) for grd in config.graders[asgn['name']] for asgn in assignments]

#TODO what happens if rudaux config doesn't have this one's name?
# TODO split this into multiple tasks each with the same signature, store a global list in this submodule and then loop over it in the flow construction
@task
def initialize_grader(config, grd_tuple):
    logger = prefect.context.get("logger")

    ta_user, grader, assignment = grd_tuple

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
    grader_path = os.path.join(config.grading_dataset_root, grader).rstrip('/')
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


    # create the submissions folder
    subms_fldr = os.path.join(grader_path, config.grading_local_collection_folder)
    if not os.path.exists(subms_fldr):
        os.makedirs(subms_fldr, exist_ok=True)
        _recursive_chown(subms_fldr, jupyter_uid)

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
    
    return grd_pair

@task
def assign_submissions(config, students, submissions, grd_tuple):
    ta_user, grader, assignment = grd_tuple

    graders = [_grader_account_name(assignment['name'], grd) for grd in config.graders[assignment['name']]]
    cur_idx = graders.index(grader)

    subms = []
    for i in range(len(students)):
        # search for this student in the grader folders 
        found = False
        for gr in graders:
            collected_asgn_path = os.path.join(config.grading_dataset_root, grader, config.grading_local_collection_folder, students[i]['id'], assignment['name'])
            if os.path.exists(collected_asgn_path):
                found = True
                if gr == grader:
                    subms.append( (grader, assignment, students[i]) )
                break
        # if not assigned, and the modulus of the student's index is the current grader
        if not found and (i % len(graders)) == cur_idx:
            # assign to this grader
            subms.append( (grader, assignment, students[i]) )

    return subms 


@task
def collect_submission(config, subm_tuple):
    grader, assignment, student = subm_tuple
    jupyter_uid = pwd.getpwnam(config.grading_jupyter_user).pw_uid
    collected_asgn_path = os.path.join(config.grading_dataset_root, grader, config.grading_local_collection_folder, student['id'], assignment['name'], assignment['name']+'.ipynb')
    due_date, override = _get_due_date(assignment, student)
    #TODO snapshot name pattern for override is hard coded...
    snap_name = assignment['name'] if override is None else assignment['name'] + '-override-' + override['id']
    snapped_asgn_path = os.path.join(config.grading_attached_student_dataset_root, student['id'], '.zfs', 'snapshot', snap_name, 
                                         config.student_local_assignment_folder, assignment['name'], assignment['name']+'.ipynb')

    if not os.path.exists(collected_assignment_path):
        shutil.copy(snapped_assignment_path, collected_assignment_path)
        os.chown(collected_assignment_path, jupyter_uid, jupyter_uid)

    return subm_tuple


@task
def clean_submission(config, subm_tuple):
    logger = prefect.context.get("logger")
    grader, assignment, student = subm_tuple
    jupyter_uid = pwd.getpwnam(config.grading_jupyter_user).pw_uid
    collected_asgn_path = os.path.join(config.grading_dataset_root, grader, config.grading_local_collection_folder, student['id'], assignment['name'], assignment['name']+'.ipynb')

    #need to check for duplicate cell ids, see
    #https://github.com/jupyter/nbgrader/issues/1083
    
    #open the student's notebook
    f = open(collected_assignment_path, 'r')
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
    f = open(collected_assignment_path, 'w')
    json.dump(nb, f)
    f.close()

    return subm_tuple

@task
def get_returnable_solutions(config, course_info, subm_tuples):
    assignment_totals = {}
    assignment_outstanding = {}
    assignment_fracs = {}
    for subm in subm_tuples:
        grader, assignment, student = subm_tuple
        anm = assignment['name']
        if anm not in assignment_totals:
            assignment_totals[anm] = 0
        if anm not in assignment_outstanding:
            assignment_outstanding[anm] = 0
        
        assignment_totals[anm] += 1
        due_date, override = _get_due_date(assignment, student)
        if due_date > plm.now():
            assignment_outstanding[anm] += 1

    for k, v in assignment_totals.items():
        assignment_fracs[k] = (v - assignment_outstanding[k])/v

    returnable_subms = []
    for subm in subm_tuples:
        grader, assignment, student = subm_tuple
        anm = assignment['name']
        if assignment_fracs[k] > config.return_solution_threshold and plm.now() > plm.parse(config.earliest_solution_return_date, tz=course_info['time_zone']):
            returnable_subms.append(subm)

    return returnable_subms

@task
def return_solution(config, subm_tuple):
    logger = prefect.context.get("logger")
    grader, assignment, student = subm_tuple

    logger.info(f"Returning solution for submission {assignment['name']}, {student['name']}")
    soln_path_grader = os.path.join(config.grading_dataset_root, grader, assignment['name'] + '_solution.html')
    soln_folder_student = os.path.join(config.grading_attached_student_dataset_root, student['id'])
    soln_path_student = os.path.join(soln_folder_student, assignment['name'] + '_solution.html')
    if not os.path.exists(soln_path_student):
        if os.path.exists(soln_folder_student):
            try:
                shutil.copy(soln_path_grader, soln_path_student) 
                jupyter_uid = pwd.getpwnam('jupyter').pw_uid
                os.chown(soln_path_student, jupyter_uid, jupyter_uid)
            except Exception as e:
                raise signals.FAIL(str(e))
        else:
            logger.warning(f"Warning: student folder {soln_folder_student} doesnt exist. Skipping solution return.")

import git
#import zfs??
from dictauth.users import _load_dict, add_user, remove_user
from collections import namedtuple
from sys import check_call

class JupyterHub(object):
    """
    Interface to a local Jupyterhub with NbGrader assignments
    """

    def __init__(self, course):
        self.jupyterhub_config_dir = course.config.jupyterhub_config_dir
        self.student_folder_root = course.config.student_folder_root
        self.assignment_folder_root = course.config.assignment_folder_root
        self.zfs_snapshot_prefix = course.config.zfs_snapshot_prefix

    def snapshot(self, name):
        check_call(['zfs', 'snapshot', '-r', self.student_folder_root + '@'+name])

    def create_grader_folder(self, grader_name):
        #make sure there isn't already a folder in /tank/home with this name; never overwrite a grader account
        epwrds = _load_dict(self.jupyterhub_config_dir)
        CreateArgs = namedtuple('CreateArgs', 'username salt digest directory')
        args = 'TODO' #CreateArgs(username = ,)
        add_user(args)


        username = 'TODO'
        callysto_user = 'jupyter'
        course = 'dsci100'
        check_call([os.path.join(self.jupyterhub_config_dir, 'zfs_homedir.sh'), course, username, callysto_user])
        pass
    
    def assign_grader(self, assignment_name, ta_username):
        #just add authentication using dictauth

    def unassign_grader(self, assignment_name):
        #just remove the authentication for the account using dictauth; don't touch the folder
        #to be called when grading is done
        pass

    def stop(self):
        pass
 
    def start(self):
        pass

    
    


    

        #======================================================#
        #    Ensure course_dir is a clean git repo and pull    #
        #======================================================#
        
        #print('Ensuring course directory is a clean git repo')
        #
        #try:
        #    repo = git.Repo(course_dir)
        #except git.exc.InvalidGitRepositoryError as e:
        #    sys.exit(f"There was an error creating a git repo object from {course_dir}.")

        ## Before we do anything, make sure our working directory is clean with no untracked files.
        #if repo.is_dirty() or repo.untracked_files:
        #  continue_with_dirty = input(
        #    """
        #    Your repository is currently in a dirty state (modifications or
        #    untracked changes are present). We strongly suggest that you resolve
        #    these before proceeding. Continue? [y/n]:"""
        #  )
        #  # if they didn't say yes, exit
        #  if continue_with_dirty.lower() != 'y':
        #    sys.exit("Exiting...")


        #print(ttbl.AsciiTable([['Pulling course repository']]).table)

        #try:
        #    repo.git.pull('origin', 'master')
        #except git.exc.GitCommandError as e:
        #    sys.exit(f"There was an error pulling the git repo from {course_dir}.")

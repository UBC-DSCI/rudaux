from dictauth.users import add_user, remove_user, get_users
from collections import namedtuple
from subprocess import check_call 

class JupyterHub(object):
    """
    Interface to Jupyterhub 
    """

    def __init__(self, config, dry_run):
        self.jupyterhub_config_dir = config.jupyterhub_config_dir
        self.dry_run = dry_run
   
    def assign_grader(self, grader_name, ta_username):
        #just add authentication using dictauth
        Args = namedtuple('Args', 'username directory copy_creds salt digest')
        args = Args(username = grader_name, directory = self.jupyterhub_config_dir, copy_creds = ta_username, salt = None, digest = None)
        if not self.dry_run:
            add_user(args)
            self.stop()
            self.start()
        else:
            print('[Dry run: would have called add_user with args ' + str(args) + ' and then restarted hub]')

    def unassign_grader(self, grader_name):
        #just remove authentication using dictauth
        Args = namedtuple('Args', 'username directory')
        args = Args(username = grader_name, directory = self.jupyterhub_config_dir)
        if not self.dry_run:
            remove_user(args)
            self.stop()
            self.start()
        else:
            print('[Dry run: would have called remove_user with args ' + str(args) + ' and then restarted hub]')

    def grader_exists(self, grader_name):
        Args = namedtuple('Args', 'directory')
        args = Args(directory = self.jupyterhub_config_dir)
        output = get_users(args)
        return (grader_name in output)

    def stop(self):
        check_call(['systemctl', 'stop', 'jupyterhub'])
 
    def start(self):
        check_call(['systemctl', 'start', 'jupyterhub'])

    

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

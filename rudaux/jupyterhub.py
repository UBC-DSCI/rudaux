import git

class JupyterHub(object):
    """
    Interface to a local Jupyterhub with NbGrader assignments
    """

    def __init__(self, course):
        self.student_folder_root = course.config.student_folder_root
        self.assignment_folder_root = course.config.assignment_folder_root
        self.zfs_snapshot_prefix = course.config.zfs_snapshot_prefix

    

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

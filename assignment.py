import requests
import re
import nbgrader
import os
import sys
import subprocess
from shutil import rmtree, copytree
from github import Github
from git import Repo
from pathlib import Path
import urllib.parse as urlparse
from typing import Union, List, Optional, Dict

from nbgrader.apps import NbGraderAPI
from traitlets.config import Config
from traitlets.config.application import Application

# from course import Course


class Assignment:
  """
  Assignment object for maniuplating assignment. This base class is blind to Canvas. 
  It only has operations for working with nbgrader. 
  """

  def __init__(
    self,
    name: str,
    path: str,
    github={
      "ins_repo_url": None,
      "stu_repo_url": None,
      "pat_name": "GITHUB_PAT"
    },
    canvas={
      "url": None,
      "course_id": None,
      "assignment": {},
      "token_name": "CANVAS_TOKEN"
      # hub_url='https://c7l1-timberst.stat.ubc.ca',
      # student_repo='https://github.ubc.ca/hinshaws/dsci_100_students',
      # hub_prefix='/jupyter'
    },
    course=None
  ) -> 'self':
    """
    Assignment object for manipulating Assignments.

    :param name: The name of the assignment.
    :param filename: The filename of the Jupyter Notebook containing the assignment. 
    :param path: The path to the notebook (in the instructors repo).
    :param pat_name: The name of your GitHub personal access token environment variable.
    :param ssh: Whether or not you will be authenticating via SSH.

    :returns: An assignment object for performing different operations on a given assignment.
    """

    # First self assign user specified parameters
    self.name = name
    self.path = path

    self.canvas_url = canvas.get('url')
    self.course_id = canvas.get('course_id')
    self.canvas_assignment = canvas.get('assignment')
    self.canvas_token_name = canvas.get('token_name')

    self.ins_repo_url = github.get('ins_repo_url')
    self.stu_repo_url = github.get('stu_repo_url')
    self.github_token_name = github.get('pat_name')

    # If we're initializing with a Canvas URL, get the Canvas Token
    if self.canvas_url is not None:
      self.canvas_token = self._get_token(canvas.get('token_name'))

    # If we're initializing with a GitHub URL, get the GitHub PAT
    if (self.ins_repo_url is not None) or (self.stu_repo_url is not None):
      self.github_pat = self._get_token(github.get('pat_name'))

  # Get the github token from the environment
  def _get_token(self, token_name: str):
    """
    Get an API token from an environment variable.
    """
    try:
      token = os.environ[token_name]
      return token
    except KeyError as e:
      print(f"You do not seem to have the '{token_name}' environment variable present:")
      raise e

  def autograde(self):
    """
    Initiate automated grading with nbgrader.
    """

    return False

  def assign(
    self,
    tmp_dir=os.path.join(Path.home(), 'tmp'),
    overwrite=False,
    # course=None #? What is the best way to have certain parts of this be abstracted if it's being called from the course object?
  ) -> 'None':
    """
    Assign assignment to students (generate student copy from instructors
    repository and push to public repository). Only provide SSH URLs if you have
    an SSH-key within sshd on this machine. Otherwise we will use your Github
    Personal Access Token.

    :param ins_repo_url: The remote URL to your instructors' repository. 
    :param stu_repo_url: The remote URL to your students' repository.
    :param tmp_dir: A temporary directory to clone your instructors repo to. 
    The default dir is located within the users directory so as to ensure write 
    permissions. 
    """

    self.overwrite = overwrite

    #=======================================#
    #                                       #
    #       Set up Parameters & Config      #
    #                                       #
    #=======================================#

    # First things first, make the temporary directories
    ins_repo_dir = os.path.join(tmp_dir, 'instructors')
    stu_repo_dir = os.path.join(tmp_dir, 'students')

    #=======================================#
    #                                       #
    #       Clone from Instructors Repo     #
    #                                       #
    #=======================================#

    try:
      self._clone_repo(self.ins_repo_url, ins_repo_dir)
    except Exception as e:
      print("There was an error cloning your instructors repository")
      raise e

    #=======================================#
    #                                       #
    #          Make Student Version         #
    #                                       #
    #=======================================#

    # Make sure we're running our nbgrader commands within our instructors repo.
    # this will contain our gradebook database, our source directory, and other
    # things.
    custom_config = Config()
    custom_config.CourseDirectory.root = ins_repo_dir

    # use the traitlets Application class directly to load nbgrader config file.
    # reference:
    # https://github.com/jupyter/nbgrader/blob/41f52873c690af716c796a6003d861e493d45fea/nbgrader/server_extensions/validate_assignment/handlers.py#L35-L37
    for config in Application._load_config_files('nbgrader_config', path=ins_repo_dir):
      # merge it with our custom config
      custom_config.merge(config)

    # set up the nbgrader api with our merged config files
    nb_api = NbGraderAPI(config=custom_config)

    # assign the given assignment!
    nb_api.assign(self.name)

    generated_assignment_dir = os.path.join(ins_repo_dir, 'release', self.name)
    student_assignment_dir = os.path.join(stu_repo_dir, self.name)
    # make sure we assigned properly
    if not os.path.exists(generated_assignment_dir):
      sys.exit(
        f"nbgrader failed to assign {self.name}, please make sure your directory structure is set up properly in nbgrader"
      )

    #=======================================#
    #                                       #
    #   Move Assignment to Students Repo    #
    #                                       #
    #=======================================#

    try:
      self._clone_repo(self.stu_repo_url, stu_repo_dir)
    except Exception as e:
      print("There was an error cloning your students repository")
      raise e

    # If the path exists...
    if os.path.exists(student_assignment_dir):
      # If we allowed for overwriting, just go ahead and remove the directory
      if self.overwrite:
        rmtree(student_assignment_dir)
      # Otherwise, ask first
      else:
        overwrite_target_dir = input(
          f"{student_assignment_dir} is not empty, would you like to overwrite? [y/n]: "
        )
        # if they said yes, remove the directory
        if overwrite_target_dir.lower() == 'y':
          rmtree(student_assignment_dir)
        # otherwise, exit
        else:
          sys.exit("Will not overwrite specified directory.\nExiting...")

    # Finally, copy to the directory, as we've removed any preexisting ones or
    # exited if we didn't want to
    copytree(generated_assignment_dir, student_assignment_dir)

    #=======================================#
    #                                       #
    #      Push Changes to Students Repo    #
    #                                       #
    #=======================================#

    self._push_repo(stu_repo_dir, self.stu_repo_url)

    return None

  def _push_repo(
    self, repo_dir: str, repo_url: str, branch='master', remote='origin'
  ) -> 'None':
    """Commit changes and push a specific repository to its remote.
    
    :param repo_dir: The location of the repository on the disk you wish to commit changes to and push to its remote.
    :type repo_dir: str
    :param repo_url: The remote url of the location you're pushing to.
    :type repo_url: str
    :param branch: The branch you wish to commit changes to.
    :type branch: str
    :param remote: The remote you with to push changes to.
    :type remote: str
    :returns: Nothing, side effects performed.
    :rtype: None
    """

    # instantiate our repository
    repo = Repo(repo_dir)
    # add all changes
    repo.git.add("--all")  # or A=True
    # get repo status with frontmatter removed. We can use regex for this
    # because the output will be consistent as we are always adding ALL changes
    repo_status = re.sub(r"(.*\n)+.+to unstage\)", "", repo.git.status())
    # Strip the whitespace at the beginning of the lines
    whitespace = re.compile(r"^\s*", re.MULTILINE)
    repo_status = re.sub(whitespace, "", repo_status)
    # And strip any preceding or trailing whitespace
    print(repo_status.strip())
    repo.git.commit("-m", f"Assigning {self.name}")

    split_url = urlparse.urlsplit(repo_url)
    if not split_url.netloc:
      # If using ssh, go ahead and clone.
      print('SSH URL detected, assuming SSH keys are accounted for.')
      print(f"Pushing changes on {branch} to {remote}...")
      repo.git.push(remote, branch)
    else:
      # Otherwise, use https url
      github_username = self._find_github_username(repo_url, self.github_pat)
      repo_url_auth = f"https://{github_username}:{self.github_pat}@{split_url.netloc}{split_url.path}.git"
      print(f"Pushing changes on {branch} to {repo_url}...")
      repo.git.push(repo_url_auth, branch)

    return None

  def collect(self):
    """
    Collect an assignment. Snapshot the ZFS filesystem and copy the notebooks to
    a docker volume for sandboxed grading.
    """

    return False

  def _clone_repo(self, repo_url: str, target_dir: str):
    """Clone a repository
    
    :param repo_url: The ssh or https url for the repository you wish to clone.
    :type repo_url: str
    :param target_dir: The directory you wish to clone your repository to.
    :type target_dir: str
    """

    # If the path exists...
    if os.path.exists(target_dir):
      # If we allowed for overwriting, just go ahead and remove the directory
      if self.overwrite:
        rmtree(target_dir)
      # Otherwise, ask first
      else:
        overwrite_target_dir = input(
          f"{target_dir} is not empty, would you like to overwrite? [y/n]: "
        )
        # if they said yes, remove the directory
        if overwrite_target_dir.lower() == 'y':
          rmtree(target_dir)
        # otherwise, exit
        else:
          sys.exit(
            "Will not overwrite specified directory, please specify an alternative directory.\nExiting..."
          )

    # Finally, make the directory, as we've removed any preexisting ones or
    # exited if we didn't want to
    os.makedirs(target_dir)

    split_url = urlparse.urlsplit(repo_url)

    print(f"Cloning from {repo_url}...")
    # If you use `urlparse` on a github ssh string, the entire result gets put
    # in 'path', leaving 'netloc' an empty string. We can check for that.
    if not split_url.netloc:
      # SO, if using ssh, go ahead and clone.
      print('SSH URL detected, assuming SSH keys are accounted for...')
      Repo.clone_from(repo_url, target_dir)

    # Otherwise, we need to get the github username from the API
    else:
      github_username = self._find_github_username(repo_url, self.github_pat)
      repo_url_auth = f"https://{github_username}:{self.github_pat}@{split_url.netloc}{split_url.path}.git"
      Repo.clone_from(repo_url_auth, target_dir)

  def _find_github_username(self, url: str, pat: str) -> 'str':
    """Find a github username through the github api.
    
    :param url: Any github or github enterprise url.
    :type url: str
    :param pat: A personal access token for the account in question.
    :type pat: str
    :return: The username of the PAT holder.
    :rtype: str
    """

    split_url = urlparse.urlsplit(url)
    # If we're trying to clone from github.com...
    if split_url.netloc == 'github.com':
      # Github() default is api.github.com
      github_username = Github(pat).get_user().login
    # Otherwise, use the GHE Domain
    else:
      github_username = Github(
        base_url=urlparse.urljoin(url, "/api/v3"), login_or_token=pat
      ).get_user().login

    return github_username

  def search_canvas_assignment(self) -> 'Dict[str, str]':
    """Find a Canvas assignment by its name.
    
    :param name: The name of the canvas assignment
    :type name: str
    :return: The canvas assignment object
    :rtype: Dict[str, str]
    """
    # Quick check to make sure we have the necessary parameters.
    if None in [self.canvas_url, self.course_id, self.canvas_token]:
      sys.exit('You must provide a canvas_url, course_id, and canvas_token.')

    existing_assignments = requests.get(
      url=urlparse.urljoin(
        self.canvas_url, f"/api/v1/courses/{self.course_id}/assignments"
      ),
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      params={"search_term": self.name}
    )

    # Make sure our request didn't fail silently
    existing_assignments.raise_for_status()
    if len(existing_assignments.json()) > 0:
      self.canvas_assignment = existing_assignments.json()[0]

    return self

  def create_canvas_assignment(self, **kwargs) -> 'None':
    """Create an assignment in Canvas.
    
    :param name: The name of the assignment
    :type name: str
    **kwargs: any parameters you wish to update on the assignment. 
      see: https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.update
    :return: None: called for side-effects.
    :rtype: None
    """

    # Quick check to make sure we have the necessary parameters.
    if None in [self.canvas_url, self.course_id, self.canvas_token]:
      sys.exit('You must provide a canvas_url, course_id, and canvas_token.')

    resp = requests.post(
      url=urlparse.urljoin(
        self.canvas_url, f"/api/v1/courses/{self.course_id}/assignments"
      ),
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={"assignment": kwargs}
    )
    # Make sure our request didn't fail silently
    resp.raise_for_status()

  def update_canvas_assignment(self, assignment_id: int, **kwargs) -> 'None':
    """
    Update an assignment.

    :param assignment_id: The Canvas ID of the assignment.
    :type assignment_id: int
    :return: None: called for side-effects.
    :rtype: None
    **kwargs: any parameters you wish to update on the assignment. 
      see: https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.update
    """

    # Quick check to make sure we have the necessary parameters.
    if None in [self.canvas_url, self.course_id, self.canvas_token]:
      sys.exit('You must provide a canvas_url, course_id, and canvas_token.')

    resp = requests.put(
      url=urlparse.urljoin(
        self.canvas_url, f"/api/v1/courses/{self.course_id}/assignments/{assignment_id}"
      ),
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={"assignment": kwargs}
    )
    # Make sure our request didn't fail silently
    resp.raise_for_status()


# class CanvasAssignment(Assignment):
#   """
#   Assignment object for maniuplating Canvas assignments. This extended class can:
#     - submit grades
#     - check due dates
#     - update assignments given new information
#   """

#   def __init__(
#     self,
#     name: str,
#     canvas_url: str,
#     course_id: int,
#     assignment_id=None,
#     canvas_token=None,
#     token_name='CANVAS_TOKEN',
#     exists_in_canvas=False
#   ):
#     if (assignment_id is None) and (name is None):
#       raise ValueError('You must supply either an assignment id or name.')

#     self.name = name

#     canvas_url = re.sub(r"\/$", "", canvas_url)
#     canvas_url = re.sub(r"^https{0,1}://", "", canvas_url)
#     self.canvas_url = canvas_url

#     self.course_id = course_id

#     if canvas_token is None:
#       self.canvas_token = self._get_token(token_name)

#     if assignment_id is not None:
#       matched_assignment = self._get_canvas_course(assignment_id)
#     else:
#       matched_assignment = self._search_canvas_course(name)

#     if matched_assignment is not None:
#       self.exists_in_canvas = True
#       # self assign canvas attributes
#       #! NOTE:
#       #! MAKE SURE THERE ARE NO NAMESPACE CONFLICTS WITH THIS
#       #!
#       self.__dict__.update(matched_assignment)
#     else:
#       self.id = None
#       self.exists_in_canvas = False

#     print(self.__dict__)

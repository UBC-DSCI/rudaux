import requests
import re
import nbgrader
import os
import subprocess
from github import Github
from git import Repo
from pathlib import Path
import urllib.parse
from typing import Union, List, Optional

# from nbgrader.apps import NbGraderAPI
# from traitlets.config import Config

# # create a custom config object to specify options for nbgrader
# config = Config()
# config.Exchange.course_id = "course101"

# nb_api = NbGraderAPI(config=config)

# # assuming source/ps1 exists
# nb_api.assign("ps1")


class Assignment:
  """
  Assignment object for maniuplating assignment. This base class is blind to Canvas. 
  It only has operations for working on things locally (nbgrader functions). 
  """

  def __init__(self, name: str, filename=None, path=None, **kwargs):
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
    self.filename = filename
    self.path = path

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
    ins_repo_url: str,
    stu_repo_url: str,
    tmp_dir=os.path.join(Path.home(), 'tmp'),
    pat_name='GITHUB_PAT'
  ):
    """
    Assign assignment to students (generate student copy from instructors repository and push to public repository). Only provide SSH URLs if you have an SSH-key within sshd on this machine. Otherwise we will use your Github Personal Access Token.

    :param ins_repo_url: The remote URL to your instructors' repository. 
    :param stu_repo_url: The remote URL to your students' repository.
    :param tmp_dir: A temporary directory to clone your instructors repo to. The default dir is located within the users directory so as to ensure write permissions. 
    """

    self.github_pat = self._get_token(pat_name)

    # First things first, make the temporary directories
    ins_repo_dir = os.path.join(tmp_dir, 'instructors')
    stu_repo_dir = os.path.join(tmp_dir, 'students')
    os.makedirs(ins_repo_dir)
    os.makedirs(stu_repo_dir)

    ins_repo_url = urllib.parse.urlsplit(ins_repo_url)
    stu_repo_url = urllib.parse.urlsplit(stu_repo_url)

    # If you use `urlparse` on a github ssh string, the entire result gets put
    # in 'path', leaving 'netloc' an empty string. We can check for that.
    if not ins_repo_url.netloc:
      # SO, if using ssh, go ahead and clone.
      print('SSH URL detected, assuming SSH keys are accounted for...')
      Repo.clone_from(urllib.parse.urlunsplit(ins_repo_url), ins_repo_dir)
    # Otherwise, we need to get the github username from the API
    else:
      # If we're trying to clone from github.com...
      if ins_repo_url.netloc == 'github.com':
        self.github_username = Github(
          base_url="https://api.github.com", login_or_token=self.github_pat
        ).get_user().login
      # Otherwise, use the GHE Domain
      else:
        self.github_username = Github(
          base_url=urllib.parse.urljoin(urllib.parse.urlunsplit(ins_repo_url), "/api/v3"),
          login_or_token=self.github_pat
        ).get_user().login
      # Finally, clone the repository!!

      ins_repo_coded = f"https://{self.github_username}:{self.github_pat}@{urllib.parse.urljoin(ins_repo_url.netloc, ins_repo_url.path)}.git"
      Repo.clone_from(ins_repo_coded, tmp_dir)

    return False

  def collect(self):
    """
    Collect an assignment. Snapshot the ZFS filesystem and copy the notebooks to a docker volume for sandboxed grading.
    """

    return False


class CanvasAssignment(Assignment):
  """
  Assignment object for maniuplating Canvas assignments. This extended class can:
    - submit grades
    - check due dates
    - update assignments given new information
  """

  def __init__(
    self,
    name: str,
    canvas_url: str,
    course_id: int,
    assignment_id=None,
    canvas_token=None,
    token_name='CANVAS_TOKEN',
    exists_in_canvas=False
  ):
    if (assignment_id is None) and (name is None):
      raise ValueError('You must supply either an assignment id or name.')

    self.name = name

    canvas_url = re.sub(r"\/$", "", canvas_url)
    canvas_url = re.sub(r"^https{0,1}://", "", canvas_url)
    self.canvas_url = canvas_url

    self.course_id = course_id

    if canvas_token is None:
      self.canvas_token = self._get_token(token_name)

    if assignment_id is not None:
      matched_assignment = self._get_canvas_course(assignment_id)
    else:
      matched_assignment = self._search_canvas_course(name)

    if matched_assignment is not None:
      self.exists_in_canvas = True
      # self assign canvas attributes
      #! NOTE:
      #! MAKE SURE THERE ARE NO NAMEING CONFLICTS WITH THIS
      #! NOTE:
      self.__dict__.update(matched_assignment)
    else:
      self.id = None
      self.exists_in_canvas = False

    print(self.__dict__)

  def _search_canvas_course(self, name):
    # Here, match the course by the name if no ID supplied
    existing_assignments = requests.get(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/assignments",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      params={"search_term": name}
    )
    # Make sure our request didn't fail silently
    existing_assignments.raise_for_status()
    if len(existing_assignments.json()) == 0:
      return None
    else:
      return existing_assignments.json()[0]

  def _get_canvas_course(self, id):
    # Here, match the course by the name if no ID supplied
    existing_assignment = requests.get(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/assignments/{id}",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )
    # Make sure our request didn't fail silently
    existing_assignment.raise_for_status()

    return existing_assignment.json()

  def create_canvas_assignment(self, name, **kwargs):
    resp = requests.post(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/assignments",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={"assignment": kwargs}
    )
    # Make sure our request didn't fail silently
    resp.raise_for_status()

  def update_canvas_assignment(self, assignment_id, **kwargs):
    """
    Update an assignment.

    :param assignment_id: The Canvas ID of the assignment.
    
    **kwargs: any parameters you wish to update on the assignment. 
      see: https://canvas.instructure.com/doc/api/assignments.html#method.assignments_api.update
    """
    resp = requests.put(
      url=
      f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/assignments/{assignment_id}",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={"assignment": kwargs}
    )
    # Make sure our request didn't fail silently
    resp.raise_for_status()
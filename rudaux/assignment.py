import pprint
import requests
import re
import nbgrader
import os
import sys
import subprocess
import urllib.parse as urlparse
import shutil
from github import Github
from git import Repo
from pathlib import Path
from typing import Union, List, Optional, Dict
from nbgrader.apps import NbGraderAPI
from nbgrader import utils as nbutils
from traitlets.config import Config
from traitlets.config.application import Application
# Import my own utility functions from this module
import rudaux
from rudaux import utils

# from course import Course


class Assignment:
  """
  Assignment object for maniuplating assignments. 
  """

  course = None

  def __init__(
    self,
    name: str,
    duedate: str,
    points: int,
    course=None,
    status='unassigned',
  ) -> 'self':
    """
    Assignment object for manipulating Assignments.

    :param name: The name of the assignment.
    :type name: str
    :param duedate: The assignment's due date.
    :type duedate: str
    :param points: The number of points the assignment is worth.
    :type points: int
    :param course: The course the assignment belongs to.
    :type course: Course

    :param status: The status of the assignment. Options: ['unassigned', 'assigned', 'collected', 'graded', 'returned']
    :type status: str

    :returns: An assignment object for performing different operations on a given assignment.
    """

    if (self.course is None) and (course is None):
      sys.exit(
        """
        The Assignment object must be instantiated with a course 
        or subclassed with a course class attribute. 

        Subclass method:
        ```
        class DSCI100Assignment(Assignment):
          course = dsci100

        homework_1 = DSCI100Assignment(
          name='homework_1',
          ...
        )
        ```

        Instantiation Method:
        ```
        homework_1 = Assignment(
          name='homework_1',
          ...
          course=dsci100
        )
        ```

        """
      )

    # First self assign user specified parameters
    self.name = name
    self.status = status

    # Only overwrite class property none present. Second check (course is not
    # None) is not necessary, since we should have exited by now if both were
    # None, but just want to be sure.
    if (self.course is None) and (course is not None):
      self.course = course

    self.launch_url = self._generate_launch_url()

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
      utils.clone_repo(self.course.ins_repo_url, ins_repo_dir, self.overwrite)
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
      utils.clone_repo(self.course.stu_repo_url, stu_repo_dir, self.overwrite)
    except Exception as e:
      print("There was an error cloning your students repository")
      raise e

    utils.safely_delete(student_assignment_dir, self.overwrite)

    # Finally, copy to the directory, as we've removed any preexisting ones or
    # exited if we didn't want to.
    # shutil.shutil.copytree doesn't need the directory to exist beforehand
    shutil.copytree(generated_assignment_dir, student_assignment_dir)

    #=======================================#
    #                                       #
    #      Push Changes to Students Repo    #
    #                                       #
    #=======================================#

    utils.push_repo(stu_repo_dir)

    return None

  def _generate_launch_url(self):
    """
    Generate assignment links for assigned assignments. 

    This will search your instructors repository for the source assignment and
    then generate the link to the student copy of the assignment.
    """

    # Given an assignment name, look in that assignment's folder and pull out
    # the notebook path. 
    #! Blindly take the first result!
    notebook = nbutils.find_all_notebooks(
      os.path.join(self.course.working_directory, 'source', self.name)
    )[0]

    # Construct launch url for nbgitpuller
    # First join our hub url, hub prefix, and launch url
    launch_url = f"{self.course.hub_url}{self.course.hub_prefix}/hub/lti/launch"
    # Then construct our nbgitpuller custom next parameter
    gitpuller_url = f"{self.course.hub_prefix}/hub/user-redirect/git-pull"
    # Finally, urlencode our repository and add that
    repo_encoded_url = urlparse.quote_plus(self.course.stu_repo_url)

    # Finally glue this all together!! Now we just need to add the subpath for each assignment
    launch_url_without_subpath = fr"{launch_url}?custom_next={gitpuller_url}%3Frepo%3D{repo_encoded_url}%26subPath%3D"

    # urlencode the assignment's subpath
    subpath = urlparse.quote_plus(f"{self.course.assignment_release_path}/{notebook}")
    # and join it to the previously constructed launch URL (hub + nbgitpuller language)
    full_launch_url = launch_url_without_subpath + subpath

    return full_launch_url

  def collect(self):
    """
    Collect an assignment. Snapshot the ZFS filesystem and copy the notebooks to
    a docker volume for sandboxed grading.
    """

    return False

  def _search_canvas_assignment(self) -> 'Dict[str, str]':
    """Find a Canvas assignment by its name.
    
    :param name: The name of the canvas assignment
    :type name: str
    :return: The canvas assignment object
    :rtype: Dict[str, str]
    """

    resp = requests.get(
      url=urlparse.urljoin(
        self.course.canvas_url, f"/api/v1/courses/{self.course.course_id}/assignments"
      ),
      headers={
        "Authorization": f"Bearer {self.course.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      params={"search_term": self.name}
    )

    first_result = resp.json()[0]

    # Check to see if we found an assignment with this name
    if len(resp.json()) > 0:
      # If we found more than one, let the user know
      if len(resp.json()) > 1:
        print(
          f"""
          Found more than one assignment, using first result, "{first_result.get('name')}".
          """
        )
      # But regardless, use the first result found
      return first_result

    else: 
      return None

    resp.raise_for_status()

  def _create_canvas_assignment(self) -> 'None':
    """Create an assignment in Canvas.
    
    :param name: The name of the assignment
    :type name: str
    :return: None: called for side-effects.
    :rtype: None
    """

    resp = requests.post(
      url=urlparse.urljoin(
        self.course.canvas_url, f"/api/v1/courses/{self.course.course_id}/assignments"
      ),
      headers={
        "Authorization": f"Bearer {self.course.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={
        "assignment": {
          "name": self.name,
          "submission_types": ['external_tool'],
          "external_tool_tag_attributes": {
            "url": self.launch_url,
            "new_tab": True,
            "content_id": self.course.external_tool_id,
            "content_type": "context_external_tool"
          }
        }
      }
    )
    resp.raise_for_status()

  def _update_canvas_assignment(self, assignment_id: int) -> 'None':
    """
    Update an assignment.

    :param assignment_id: The numeric ID of the assignment in Canvas
    :type assignment_id: int
    :return: No return, called for side-effects.
    :rtype: None
    """

    resp = requests.put(
      url=urlparse.urljoin(
        self.course.canvas_url,
        f"/api/v1/courses/{self.course.course_id}/assignments/{assignment_id}"
      ),
      headers={
        "Authorization": f"Bearer {self.course.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={
        "assignment": {
          "submission_types": ['external_tool'],
          "external_tool_tag_attributes": {
            "url": self.launch_url,
            "new_tab": True,
            "content_id": self.course.external_tool_id,
            "content_type": "context_external_tool"
          }
        }
      }
    )

    # Make sure our request didn't fail silently
    resp.raise_for_status()

  def update_or_create_canvas_assignment(self) -> 'str':
    """Update or create an assignment, depending on whether or not it was found
    """

    canvas_assignment = self._search_canvas_assignment()
    
    if canvas_assignment: 
      self._update_canvas_assignment(canvas_assignment.get('id'))
      return 'updated'
    else: 
      self._create_canvas_assignment()
      return 'created'


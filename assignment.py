import requests
import re
import nbgrader
from os import environ
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
    Users must specify a course ID, but if the assignment is not yet in Canvas, 
    it will not have an assignment ID (which is therefore optional).

    :param course_id: The (numeric) Canvas Course ID. 
    :param canvas_url: Base URL to your Canvas deployment. Probably something like "canvas.institution.edu".
    :param token_env_name: The name of your Canvas Token environment variable. 

    For a full list of possible kwargs, please see the Canvas API docs:
    https://canvas.instructure.com/doc/api/assignments.html#Assignment

    :returns: An assignment object for performing different operations on a given assignment.
    """

    # First self assign user specified parameters
    self.name = name
    self.filename = filename
    self.path = path

  def autograde(self):
    """
    Initiate automated grading with nbgrader.
    """

    return False

  def assign(self):
    """
    Assign assignment to students (generate student copy from instructors repository and push to public repository).
    """

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

  # Get the canvas token from the environment
  def _get_token(self, token_name: str):
    """
    Get an API token from an environment variable.
    """
    try:
      token = environ[token_name]
      return token
    except KeyError as e:
      print(f"You do not seem to have the '{token_name}' environment variable present:")
      raise e

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
#!/usr/bin/env python3

import requests
import re
from os import environ
from typing import Union, List, Optional


class Assignment:
  """
  Assignment object for manipulating Canvas assignments
  """

  def __init__(
    self,
    name: str,
    course_id: Union[str, int],
    canvas_url: str,
    assignment_id=None,
    filename=None,
    path=None,
    canvas_token=None,
    token_name='CANVAS_TOKEN',
    exists_in_canvas=False,
    **kwargs
  ):
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

    if (assignment_id is None) and (name is None):
      raise ValueError('You must supply either an assignment id or name.')

    # First self assign user specified parameters
    self.course_id = course_id
    self.name = name
    self.filename = filename
    self.path = path

    canvas_url = re.sub(r"\/$", "", canvas_url)
    canvas_url = re.sub(r"^https{0,1}://", "", canvas_url)
    self.canvas_url = canvas_url

    if canvas_token is None:
      self.canvas_token = self._get_token(token_name)

    if assignment_id is not None:
      self.assignment_id = assignment_id
      self.exists_in_canvas = True
    else:
      matched_assignment_id = self._find_course_in_canvas(name)
      if matched_assignment_id is not None:
        self.assignment_id = matched_assignment_id
        self.exists_in_canvas = True
      else:
        self.assignment_id = None
        self.exists_in_canvas = False

    # self assign any remaining parameters from kwargs
    self.__dict__.update(kwargs)

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

  def _find_course_in_canvas(self, name):
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

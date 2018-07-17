#!/usr/bin/env python3

import requests


class Assignment:
  """
  Assignment object for manipulating Canvas assignments
  """

  def __init__(self, course_id, canvas_url, assignment_id, name):
    """
    Users must specify a course ID, but can specify either an assignment name or
    assignment ID.

    :param course_id: The (numeric) Canvas Course ID. 
    :param canvas_url: Base URL to your Canvas deployment. Probably something like "canvas.institution.edu".
    :param token_env_name: The name of your Canvas Token environment variable. 

    :returns: A Course object for performing operations on an entire course at once.
    """
    self.course_id = course_id
    self.name = name
    if assignment_id:
      self.assignment_id = assignment_id
    else:
      self.assignment_id = self._find_course(name)

  def change_course_url(self, url):
    # requests.get()
    print('URL Updated')

  def _find_course(self, name):
    # Here, match the course by the name if no ID supplied
    print('Here is the assignment ID')
    return (1)

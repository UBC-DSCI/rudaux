#!/usr/bin/env python3

import requests


class Assignment:
  """
  Assignment object for manipulating Canvas assignments
  """

  def __init__(self, course_id=None, assignment_id=None, name=None):
    self.course_id = course_id
    self.name = name
    if assignment_id:
      self.assignment_id = assignment_id
    else:
      self.assignment_id = self._findCourse(name)

  def changeCourseURL(self, url):
    # requests.get()
    print('URL Updated')

  def _findCourse(self, name):
    # Here, match the course by the name if no ID supplied
    print('Here is the assignment ID')
    return (1)

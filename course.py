#!/usr/bin/env python3

# This will be called by cron and run after assignment closes

import requests
import os
import nbgrader

# We take in the Canvas course ID as an argument and run that


class Course():
  """
  Course object for manipulating Canvas courses
  """

  def __init__(self, id, token_env_name='CANVAS_TOKEN'):
    self.id = id
    self.canvas_token = self._getToken(token_env_name)

  # Get the canvas token from the environment
  def _getToken(self, token_env_name='CANVAS_TOKEN'):
    try:
      canvas_token = os.environ[token_env_name]
      return canvas_token
    except KeyError as e:
      print("You do not seem to have the 'CANVAS_TOKEN' environment variable present.", e)
      raise

  def getStudents(self):
    # List all of the students in the course
    resp = requests.get(
      url=f"https://ubc.test.instructure.com/api/v1/courses/{self.id}/users",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={
        # NOTE: student and teacher here just for the time being
        # Canvas API is being funky, so using both for the moment, for testing
        "enrollment_type": ["student", "teacher"]
      },
    )
    if (resp.status_code != 200):
      print("There was an error querying the Canvas API.", resp.json())
    else:
      # pull out the response JSON
      students = resp.json()
      # And get the LTI ID for each. Because the map object appends the LTI ID
      # to the student object passed in and returns the entire object, we can
      # simply pass in our students and get the modified object back.
      # Reassigning to the students object here... is this frowned upon?
      students = list(map(self._getStudentLTI, students))
      self.students = students
      return self

  def _getStudentLTI(self, student):
    """ 
    Take in a student object, find the student's LTI ID. Then append that ID to
    the student object passed in and return the student object.
    """
    resp = requests.get(
      url=f"https://ubc.test.instructure.com/api/v1/users/{student['id']}/profile",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )
    # If we didn't run into an unauthorized error, then we can check the object
    # for an LTI ID. UNFORTUNATELY, we are getting an error for Tiffany's
    # profile. This likely indicates that an LTI ID is not generated for a user
    # unless an LTI Launch link has been clicked by the student. HOWEVER, this
    # should not be a problem as by the time we will be running this autograde
    # script, we would expect all the students to have launched (and hopefully
    # completed!) an assignment.
    if (resp.status_code == 200):
      # Get the response content--the student's profile
      student_profile = resp.json()
      # Then check for the key
      if 'lti_user_id' in student_profile:
        # And append it to our students object
        student['lti_user_id'] = student_profile['lti_user_id']

    # Here we have elected to simply not append the lti_user_id if we didn't
    # find one. We could also decide to append our own value if not found (i.e.
    # None, 0, 'not_found', etc.).

    # Then return the students object
    return student
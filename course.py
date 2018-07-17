#!/usr/bin/env python3

# This will be called by cron and run after assignment closes

import requests
import os
import re
# import nbgrader
# For progress bar
from tqdm import tqdm
from weir import zfs
from github import Github
# For setting up autograding
from crontab import CronTab
from assignment import Assignment
from dateutil.parser import parse

#* All internal _methods() return an object
#* All external  methods() return self (are chainable), and mutate object state


# Must be instantiated with a course ID
class Course:
  """
  Course object for manipulating an entire Canvas course
  """

  def __init__(self, course_id: int, canvas_url: str, token_name='CANVAS_TOKEN'):
    """
    :param course_id: The (numeric) Canvas Course ID. 
    :param canvas_url: Base URL to your Canvas deployment. Probably something like "canvas.institution.edu".
    :param token_name: The name of your Canvas Token environment variable. 

    :returns: A Course object for performing operations on an entire course at once.
    """
    # remove trailing slashes from url
    cleaned_canvas_url = re.sub(r"\/$", "", canvas_url)
    # remove http(s)://
    cleaned_canvas_url = re.sub(r"^https{0,1}://", "", cleaned_canvas_url)
    self.course_id = course_id
    self.canvas_url = cleaned_canvas_url
    self.canvas_token = self._get_token(token_name)
    self.course = self._get_course()
    self.cron = CronTab(user=True)

  # Get the canvas token from the environment
  def _get_token(self, token_name='CANVAS_TOKEN'):
    """
    Get the Canvas API token from an environment variable.
    """
    try:
      canvas_token = os.environ[token_name]
      return canvas_token
    except KeyError as e:
      print("You do not seem to have the 'CANVAS_TOKEN' environment variable present:")
      raise e

  def _get_course(self):
    """
    Get the basic course information from Canvas
    """
    resp = requests.get(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )
    if (resp.status_code != 200):
      print("There was an error querying the Canvas API.", resp.json())
    else:
      # pull out the response JSON
      course = resp.json()
      return course

  def get_students(self):
    """
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    Get the student list for a course. 
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    """
    print('Querying list of students...')
    # List all of the students in the course
    resp = requests.get(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/users",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      },
      json={
        #! NOTE: student AND teacher here just for the time being. The Canvas
        #! API is being funky, so using both for the moment for testing
        "enrollment_type": ["student", "teacher"]
      },
    )
    if (resp.status_code != 200):
      print("There was an error querying the Canvas API.", resp.json())
    else:
      # pull out the response JSON
      students = resp.json()
      # This chunk is unnecessary, see comment above `_get_student_lti()` def.

      # And get the LTI ID for each. Because the map object appends the LTI ID
      # to the student object passed in and returns the entire object, we can
      # simply pass in our students and get the modified object back.
      # Use `tqdm` progress bar
      # print('Querying student IDs...')
      # students = list(map(self._getStudentLTI, tqdm(students)))

      # debug statements:
      # num_with_id = sum(1 for stu in students if 'lti_user_id' in stu)
      # print(f"{num_with_id}/{len(students)} students have an LTI user ID.")

      self.students = students
      return self

  # `_get_student_lti()` actually only works if you have the permission to
  # masquerade as another user. This is potentially even less secure than
  # running your external tool in public mode, and UBC locks down this
  # permission. Therefore, we will run our tool in public mode and update
  # `ltiauthenticator` to be able to use the `custom_canvas_id` parameter if it
  # exists.

  # def _get_student_lti(self, student):
  #   """
  #   Take in a student object, find the student's LTI ID. Then append that ID to
  #   the student object passed in and return the student object.
  #   """
  #   resp = requests.get(
  #     url=f"https://{self.canvas_url}/api/v1/users/{student['id']}/profile",
  #     headers={
  #       "Authorization": f"Bearer {self.canvas_token}",
  #       "Accept": "application/json+canvas-string-ids"
  #     }
  #   )
  #   # If we didn't run into an unauthorized error, then we can check the object
  #   # for an LTI ID. UNFORTUNATELY, we are getting an error for Tiffany's
  #   # profile. This likely indicates that an LTI ID is not generated for a user
  #   # unless an LTI Launch link has been clicked by the student. HOWEVER, this
  #   # should not be a problem as by the time we will be running this autograde
  #   # script, we would expect all the students to have launched (and hopefully
  #   # completed!) an assignment.
  #   if (resp.status_code == 200):
  #     # Get the response content--the student's profile
  #     student_profile = resp.json()
  #     # Then check for the key
  #     if 'lti_user_id' in student_profile:
  #       # And append it to our students object
  #       student['lti_user_id'] = student_profile['lti_user_id']

  #   # Here we have elected to simply not append the lti_user_id if we didn't
  #   # find one. We could also decide to append our own value if not found (i.e.
  #   # None, 0, 'not_found', etc.).

  #   # Then return the students object
  #   return student

  def get_assignments_from_canvas(self):
    """
    Get all assignments for a course.
    """
    resp = requests.get(
      url=f"https://{self.canvas_url}/api/v1/courses/{self.course_id}/assignments",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )

    if (resp.status_code != 200):
      print("There was an error querying the Canvas API.", resp.json())
    else:
      # pull out the response JSON
      assignments = resp.json()
      print(type(assignments))
      print(assignments)
      self.assignments = assignments

    return self

  def schedule_grading(self):
    """
    Schedule assignment grading tasks in crontab. 
    It would probably make more sense to use `at` instead of `cron` except that:
      1. CentOS has `cron` by default, but not `at`
      2. The python CronTab module exists to make this process quite easy.
    """
    # If there is no 'lock at' time, then the due date is the time to grade.
    # Otherwise, grade at the 'lock at' time. This is to allow partial credit
    # for late assignments.
    # Reference: https://community.canvaslms.com/docs/DOC-10327-415273044
    for assignment in tqdm(self.assignments):
      self._schedule_assignment_grading(assignment)
    print('Grading scheduled!')

  def _schedule_assignment_grading(self, assignment):
    job = self.cron.new(
      command=f"nbgrader collect {assignment.get('name')}",
      comment=f"Autograde {assignment.get('name')}"
    )

    if assignment.get('lock_at') is not None:
      close_time = parse(assignment['lock_at'])

    elif assignment.get('due_at') is not None:
      close_time = parse(assignment['due_at'])

    elif self.course.get('end_at') is not None:
      close_time = parse(self.course['end_at'])

    else:
      close_time: None
      print(
        'Could not find an end date for your course in Canvas, automatic grading will not be scheduled.'
      )

    # * Make sure we don't have a job for this already, and then set it if it's valid
    existing_jobs = self.cron.find_command(f"nbgrader collect {assignment.get('name')}")

    # wonky syntax because find_command & find_comment return *generators*
    if (len(list(existing_jobs)) > 0) & job.is_valid():
      # Set job
      job.setall(close_time)
      self.cron.write()
    else:
      # delete previous command here
      # then set job
      job.setall(close_time)
      self.cron.write()

#!/usr/bin/env python3

# This will be called by cron and run after assignment closes

import requests
import os
# import nbgrader
# For progress bar
from tqdm import tqdm
# For setting up autograding
from crontab import CronTab
from assignment import Assignment
from dateutil.parser import parse

#* All internal _methods() return an object
#* All external  methods() return self (are chainable), and mutate object state


# Must be instantiated with a course ID
class Course:
  """
  Course object for manipulating Canvas courses
  """

  def __init__(self, course_id, token_env_name='CANVAS_TOKEN'):
    self.course_id = course_id
    self.canvas_token = self._getToken(token_env_name)
    self.course = self._getCourse()
    self.cron = CronTab(user=True)

  # Get the canvas token from the environment
  def _getToken(self, token_env_name='CANVAS_TOKEN'):
    """
    Get the Canvas API token from an environment variable.
    """
    try:
      canvas_token = os.environ[token_env_name]
      return canvas_token
    except KeyError as e:
      print("You do not seem to have the 'CANVAS_TOKEN' environment variable present.", e)
      raise

  def _getCourse(self):
    """
    Get your course information
    """
    resp = requests.get(
      url=f"https://ubc.test.instructure.com/api/v1/courses/{self.course_id}",
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

  def getStudents(self):
    """
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    Get the student list for a course. 
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    """
    print('Querying list of students...')
    # List all of the students in the course
    resp = requests.get(
      url=f"https://ubc.test.instructure.com/api/v1/courses/{self.course_id}/users",
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
      # And get the LTI ID for each. Because the map object appends the LTI ID
      # to the student object passed in and returns the entire object, we can
      # simply pass in our students and get the modified object back.
      # Reassigning to the students object here... is this frowned upon?
      # Use `tqdm` progress bar
      print('Querying student IDs...')
      students = list(map(self._getStudentLTI, tqdm(students)))
      num_with_id = sum(1 for stu in students if 'lti_user_id' in stu)
      print(f"{num_with_id}/{len(students)} students have an LTI user ID.")
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

  def getAssignments(self):
    """
    Get all assignments for a course.
    """
    resp = requests.get(
      url=f"https://ubc.test.instructure.com/api/v1/courses/{self.course_id}/assignments",
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )

    if (resp.status_code != 200):
      print("There was an error querying the Canvas API.", resp.json())
    else:
      # pull out the response JSON
      # assignments = resp.json()
      self.assignments = resp.json()

    return self

  def scheduleGrading(self):
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
      self._scheduleAssignment(assignment)
    print('Grading scheduled!')

  def _scheduleAssignment(self, assignment):
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
        'Could not find an end date for your course, automatic grading will not be scheduled'
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

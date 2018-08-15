import pprint
import requests
import re
import nbgrader
import os
import sys
import subprocess
import shutil
import pendulum
import time
import urllib.parse as urlparse

from terminaltables import AsciiTable, SingleTable
from dateutil.parser import parse
from weir import zfs
from pathlib import Path
from typing import Union, List, Optional, Dict

from nbgrader.apps import NbGraderAPI
from nbgrader import utils as nbutils
from nbgrader.converters.base import NbGraderException

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
    duedate=None,
    duetime=None,
    points=1,
    manual=False,
    course=None,
    status='unassigned',
  ) -> 'self':
    """
    Assignment object for manipulating Assignments.

    :param name: The name of the assignment.
    :type name: str
    :param duedate: The assignment's due date. (default: None)
    :type duedate: str
    :param duedate: The assignment's due time. (default: None)
    :type duedate: str
    :param points: The number of points the assignment is worth. (default: 1)
    :type points: int
    :param manual: Is manual grading required? (default: False)
    :type manual: bool
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
    self.points = points
    self.manual = manual

    # Only overwrite class property none present. Second check (course is not
    # None) is not necessary, since we should have exited by now if both were
    # None, but just want to be sure.
    if (self.course is None) and (course is not None):
      self.course = course

    #============================#
    #      Datetime Parsing      #
    #============================#

    # Due date is passed in from config file as a string we need to parse this
    # and convert it to ISO 8601 format with the course timezone. Pendulum will
    # handle daylight savings time for us!
    self.duedate = pendulum.parse(f"{duedate}T{duetime}", tz=self.course.course_timezone)
    # We need to convert the course due date to the server/system due date as
    # well, so that our cron job will run at the correct time.
    self.system_due_date = self.duedate.in_tz(self.course.system_timezone)

    self.launch_url = self._generate_launch_url()

  def autograde(self):
    """
    Initiate automated grading with nbgrader.
    """

    return False

  # def assign(
  #   self,
  #   tmp_dir=os.path.join(Path.home(), 'tmp'),
  #   overwrite=False,
  # ) -> 'None':
  #   """
  #   Assign assignment to students (generate student copy from instructors
  #   repository and push to public repository). Only provide SSH URLs if you have
  #   an SSH-key within sshd on this machine. Otherwise we will use your Github
  #   Personal Access Token.

  #   :param tmp_dir: A temporary directory to clone your instructors repo to. 
  #   The default dir is located within the users directory so as to ensure write 
  #   permissions. 
  #   """

  #   self.overwrite = overwrite

  #   #=======================================#
  #   #       Set up Parameters & Config      #
  #   #=======================================#

  #   # First things first, make the temporary directories
  #   ins_repo_dir = os.path.join(tmp_dir, 'instructors')
  #   stu_repo_dir = os.path.join(tmp_dir, 'students')

  #   #=======================================#
  #   #       Clone from Instructors Repo     #
  #   #=======================================#

  #   try:
  #     utils.clone_repo(self.course.ins_repo_url, ins_repo_dir, self.overwrite)
  #   except Exception as e:
  #     print("There was an error cloning your instructors repository")
  #     raise e

  #   #=======================================#
  #   #          Make Student Version         #
  #   #=======================================#

  #   # Make sure we're running our nbgrader commands within our instructors repo.
  #   # this will contain our gradebook database, our source directory, and other
  #   # things.
  #   custom_config = Config()
  #   custom_config.CourseDirectory.root = ins_repo_dir

  #   # use the traitlets Application class directly to load nbgrader config file.
  #   # reference:
  #   # https://github.com/jupyter/nbgrader/blob/41f52873c690af716c796a6003d861e493d45fea/nbgrader/server_extensions/validate_assignment/handlers.py#L35-L37
  #   for config in Application._load_config_files('nbgrader_config', path=ins_repo_dir):
  #     # merge it with our custom config
  #     custom_config.merge(config)

  #   # set up the nbgrader api with our merged config files
  #   nb_api = NbGraderAPI(config=custom_config)

  #   # assign the given assignment!
  #   nb_api.assign(self.name)

  #   generated_assignment_dir = os.path.join(ins_repo_dir, 'release', self.name)
  #   student_assignment_dir = os.path.join(stu_repo_dir, self.name)
  #   # make sure we assigned properly
  #   if not os.path.exists(generated_assignment_dir):
  #     sys.exit(
  #       f"nbgrader failed to assign {self.name}, please make sure your directory structure is set up properly in nbgrader"
  #     )

  #   #=======================================#
  #   #   Move Assignment to Students Repo    #
  #   #=======================================#

  #   try:
  #     utils.clone_repo(self.course.stu_repo_url, stu_repo_dir, self.overwrite)
  #   except Exception as e:
  #     print("There was an error cloning your students repository")
  #     raise e

  #   utils.safely_delete(student_assignment_dir, self.overwrite)

  #   # Finally, copy to the directory, as we've removed any preexisting ones or
  #   # exited if we didn't want to.
  #   # shutil.shutil.copytree doesn't need the directory to exist beforehand
  #   shutil.copytree(generated_assignment_dir, student_assignment_dir)

  #   #=======================================#
  #   #      Push Changes to Students Repo    #
  #   #=======================================#

  #   utils.push_repo(stu_repo_dir)

  #   #=======================================#
  #   #        Update Assignment Status       #
  #   #=======================================#

  #   self.status = 'assigned'

  #   return None

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
    repo_encoded_url = urlparse.quote_plus(self.course.stu_launch_url)

    # Finally glue this all together!! Now we just need to add the subpath for each assignment
    launch_url_without_subpath = fr"{launch_url}?custom_next={gitpuller_url}%3Frepo%3D{repo_encoded_url}%26subPath%3D"

    # urlencode the assignment's subpath
    subpath = urlparse.quote_plus(f"{self.course.assignment_release_path}/{notebook}")
    # and join it to the previously constructed launch URL (hub + nbgitpuller language)
    full_launch_url = launch_url_without_subpath + subpath

    return full_launch_url

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

    # Check to see if we found an assignment with this name
    if len(resp.json()) > 0:
      first_result = resp.json()[0]
      # If we found more than one, let the user know
      if len(resp.json()) > 1:
        print(
          f"""
          Found more than one assignment, using first result, "{first_result.get('name')}".
          """
        )
      # But regardless, use the first result found
      # Also assign to self
      self.canvas_assignment = first_result
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
          "due_at": self.duedate.to_iso8601_string(),
          "points_possible": self.points,
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
          "due_at": self.duedate.to_iso8601_string(),
          "points_possible": self.points,
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

    self.canvas_assignment = self._search_canvas_assignment()
    
    if self.canvas_assignment: 
      self._update_canvas_assignment(self.canvas_assignment.get('id'))
      return f'{utils.color.PURPLE}updated{utils.color.END}'
    else: 
      self._create_canvas_assignment()
      return f'{utils.color.DARKCYAN}created{utils.color.END}'

  def schedule_grading(self) -> 'Assignment':
    """Schedule grading of an assignment.
    
    :param cron: Crontab of your server
    :type cron: Cron
    :return: self
    :rtype: Assignment
    """

    # Initialize dict for status reporting
    status = {}

    # Initialize an empty value for close_time
    close_time = ''

    # =================================== #
    #     Find Due Date (Close Time)      #
    # =================================== #

    # NOTE: Because we are SCHEDULING our grading for the server here, 
    # we need to use the system time, not the course time.

    # If we found the assignment in Canvas, we can look for a lock date.
    if hasattr(self, 'canvas_assignment') and self.canvas_assignment is not None:

      if self.canvas_assignment.get('lock_at') is not None:
        # Canvas uses UTC
        close_time = pendulum \
          .parse(self.canvas_assignment.get('lock_at'), tz='UTC') \
          .in_tz(self.course.system_timezone)

      elif self.canvas_assignment.get('due_at') is not None:
        # Canvas uses UTC
        close_time = pendulum \
          .parse(self.canvas_assignment.get('due_at'), tz='UTC') \
          .in_tz(self.course.system_timezone)

    # if both of those came back as none, or we haven't hit the 
    # Canvas API, use our own due date, as determined when the 
    # Assignment was instantiated (with the from the date from
    # the config object)

    # Otherwise, check for a due date set from our config file.
    # ('' and None are both Falsey)
    if (not close_time) and self.system_due_date is not None:
      close_time = self.system_due_date

    # If we STILL haven't found a due date by now, skip scheduling grading!!
    if not close_time:
      print(
        f'Could not find a due date or lock date for {self.name}, automatic grading will not be scheduled.'
      )
      status['close_time'] = 'None'
      status['action'] = 'None'
      
      # Exit early if no due date found!
      return status

    # ============================================== #
    #     Done looking for due date (close time)     #
    # ============================================== #

    # pretty print the due date/close_time in the course timezone
    status['close_time'] = close_time \
      .in_tz(self.course.course_timezone) \
      .to_day_datetime_string()

    # Could potentially fall back to closing at course end date, but doesn't seem particularly helpful
    # elif self.course.get('end_at') is not None:
    #   close_time = parse(self.course['end_at'])

    # Make sure we don't have a job for this already, and then set it if it's valid

    # convert generator to list so we can iterate over it multiple times
    existing_jobs = list(self.course.cron.find_comment(f"Autograde {self.name}"))

    # Check to see if we found any preexisting jobs
    if (len(list(existing_jobs)) > 0):
      status['action'] = f'{utils.color.PURPLE}updated{utils.color.END}'

      # if so, delete the previously scheduled jobs before setting a new command
      for job in existing_jobs:  
        self.course.cron.remove(job)

    # Otherwise just go ahead and set the job
    else:
      status['action'] = f'{utils.color.DARKCYAN}created{utils.color.END}'

    # If we require manual grading, set the flag
    man_graded = ' -m' if self.manual else ''

    # Construct the grade command for cron to run
    grade_command = f"rudaux grade '{self.name}' --dir {self.course.working_directory}{man_graded}"

    # Then add our new job
    new_autograde_job = self.course.cron.new(
      command=grade_command,
      comment=f"Autograde {self.name}"
    )
    # Make sure it's valid...
    if new_autograde_job.is_valid():
      # And set it!
      new_autograde_job.setall(close_time)
      self.course.cron.write()
    else: 
      status['action'] = 'failed'
      print(f'Automatic grading for {self.name} failed due to invalid cron job formatting:')
      print(new_autograde_job)
    
    return status

  # These functions are intended only to be run from commands.grade(), 
  # which is intended only to be run from a system-level crontab
  # OR with sudo permissions.
  # def snapshot_zfs(self):
  #   """Snapshot the ZFS filesystem.
    
  #   """

  #   # construct command for zfs.
  #   # ZFS refers to its 'datasets' without a preceding slash
  #   dataset = re.sub('^/', '', self.course.storage_path)
  #   snapshot_name = f"{dataset}@{self.name}"

  #   # Now, we can use Weir to check for preexisting snapshots
  #   existing_snapshots = zfs.open(dataset).snapshots()

  #   # The whole reason we are doing this is because our snapshot names must be unique
  #   # So if we DO have a hit, there can only be one!
  #   preexisting_snapshots = list(filter(lambda snap: snap.name == snapshot_name, existing_snapshots))

  #   # so if we have a hit, get the date of that snap
  #   if len(preexisting_snapshots) > 0:
  #     preexisting_snapshot = preexisting_snapshots[0]
  #     snap_date = preexisting_snapshot.getprop('creation').get('value')
  #     snap_time = time.strftime(r'%Y-%m-%d %H:%M:%S', time.localtime(int(snap_date)))
  #     print(f'Using preexisting snapshot for this assignment created at {snap_time} (server time).')
  #   else: 
  #     # we'll name the snapshot after the assignment being graded
  #     #! I feel like we can't run a sudo command from the user crontab
  #     subprocess.run(["sudo", "zfs", "snapshot", snapshot_name], check=True)

  def collect(self):
    """
    Collect an assignment via the nbgrader API.
    This essentially copies the notebooks to a new location
    """

    try:
      student_ids = map(lambda stu: stu.get('id'), self.course.students)
    except Exception:
      sys.exit("No students found. Please run `course.get_students_from_canvas()` before collecting an assignment.")

    if self.course.zfs:
      # This is the snapshot name for this assignment. This may be an hourly
      # snapshot that corresponds to the due date, or it might be the
      # assignment name.
      snapshot_name = self.name
      zfs_path = os.path.join(
        '.zfs', 
        'snapshot', 
        snapshot_name
      )

    assignment_collection_header = [
      ['Student ID', 'Collection Status']
    ]
    assignment_collection_status = []

    # get the assignment path for each student ID in Canvas
    for student_id in student_ids:

      student_path = os.path.join(
        self.course.storage_path,
        student_id,
        self.course.stu_repo_name,
        self.course.assignment_release_path
      )

      # If zfs, use the student + zfs + assignment name path
      if self.course.zfs and os.path.exists(os.path.join(student_path, '.zfs')):
        # Check that we're using ZFS
        assignment_path = os.path.join(
          student_path, 
          zfs_path
          # self.name
        )
      # otherwise just use the student's work directly
      else:
        assignment_path = os.path.join(
          student_path
          # self.name
        )

      submission_path = os.path.join(self.course.working_directory, 'submitted', student_id)
      # then copy the work into the submitted directory + student_id + assignment_name
      try:
        shutil.copytree(assignment_path, submission_path)
      # if no assignment for that student, fail
      #* NOTE: could also be due to incorrect directory structure.
      except FileNotFoundError:
        assignment_collection_status.append([student_id, f'{utils.color.RED}failure{utils.color.END}'])
      else: 
        assignment_collection_status.append([student_id, f'{utils.color.GREEN}success{utils.color.END}'])

    table = SingleTable(assignment_collection_header + assignment_collection_status)
    table.title = 'Assignment Collection'
    print(table.table)

    # What I just did WAS collecting the assignment.
    # Finally, collect the assignment
    # res = self.course.nb_api.collect(self.name)

    # if res.get('success'):
    #   print(f'Successfully collected {self.name}.')
    # if res.get('error') is not None:
    #   print(f'There was an error collecting {self.name}.')
    #   print(res.get('error'))
    # if res.get('log') is not None:
    #   print(f'Log result of collecting {self.name}.')
    #   print(res.get('log'))

    # Commit repo
    # Push Repo

    return self

  def grade(self):
    """
    Autograde an assignment via the nbgrader API.
    This essentially run `nbgrader autograde`.
    """

    assn_grade_header = [
      ['Student ID', 'Grading Status']
    ]
    assn_grade_status = []

    try:
      student_ids = map(lambda stu: stu.get('id'), self.course.students)
    except Exception:
      sys.exit("No students found. Please run `course.get_students_from_canvas()` before collecting an assignment.")

    for student_id in student_ids:
      try:
        res = self.course.nb_api.autograde(
          assignment_id=self.name,
          student_id=student_id
        )
      except NbGraderException:
        print(res.get('error'))
        assn_grade_status.append([student_id, f'{utils.color.RED}failure{utils.color.END}'])
      else:
        print(res.get('success'))
        assn_grade_status.append([student_id, f'{utils.color.GREEN}success{utils.color.END}'])

    table = SingleTable(assn_grade_header + assn_grade_status)
    table.title = 'Assignment Grading'
    print(table.table)

    # Commit repo
    # Push repo
    return self

  def feedback(self):
    """
    Generate feedback reports for student assignments.  
    """

    assn_feedback_header = [
      ['Student ID', 'Feedback Status']
    ]
    assn_feedback_status = []  

    try:
      student_ids = map(lambda stu: stu.get('id'), self.course.students)
    except Exception:
      sys.exit("No students found. Please run `course.get_students_from_canvas()` before collecting an assignment.")

    for student_id in student_ids:
      res = self.course.nb_api.feedback(
        assignment_id=self.name,
        student_id=student_id
      )
      if res.get('success'):
        assn_feedback_status.append([student_id, f'{utils.color.GREEN}success{utils.color.END}'])
      elif res.get('error') is not None:
        print(res.get('error'))
        assn_feedback_status.append([student_id, f'{utils.color.RED}failure{utils.color.END}'])
      else:
        print(res.get('log'))
        assn_feedback_status.append([student_id, 'error (see log)'])

    table = SingleTable(assn_feedback_header + assn_feedback_status)
    table.title = 'Assignment Feedback'
    print(table.table)

    # Commit Repo
    # Push Repo
    return self

  def submit(self):
    """
    Upload grades to Canvas.  
    """

    print('submitting...')

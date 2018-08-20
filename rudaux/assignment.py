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

from terminaltables import AsciiTable
from dateutil.parser import parse
from pathlib import Path
from typing import Union, List, Optional, Dict

from nbgrader.apps import NbGraderAPI
from nbgrader import utils as nbutils
# This is not working properly for some reason
# from nbgrader.converters.base import NbGraderException

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
  ) -> 'self':
    """
    Assignment object for manipulating Assignments.

    :param name: The name of the assignment.
    :type name: str
    :param duedate: The assignment's due date. (default: None)
    :type duedate: str
    :param duetime: The assignment's due time. (default: None)
    :type duetime: str
    :param points: The number of points the assignment is worth. (default: 1)
    :type points: int
    :param manual: Is manual grading required? (default: False)
    :type manual: bool
    :param course: The course the assignment belongs to.
    :type course: Course

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

  #   return self

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

    return resp.json()

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

    return resp.json()

  def update_or_create_canvas_assignment(self) -> 'str':
    """Update or create an assignment, depending on whether or not it was found
    """

    self.canvas_assignment = self._search_canvas_assignment()
    
    if self.canvas_assignment: 
      self.canvas_assignment = self._update_canvas_assignment(self.canvas_assignment.get('id'))
      return f'{utils.color.PURPLE}updated{utils.color.END}'
    else: 
      self.canvas_assignment = self._create_canvas_assignment()
      return f'{utils.color.DARKCYAN}created{utils.color.END}'

  def schedule_grading(self) -> 'Assignment':
    """Schedule grading of an assignment.
    
    :return: self
    :rtype: Assignment
    """

    # Initialize dict for status reporting
    scheduling_status = {}

    # Initialize an empty value for close_time
    close_time = ''

    # =================================== #
    #     Find Due Date (Close Time)      #
    # =================================== #

    # NOTE: Because we are SCHEDULING our grading for the server here, 
    # we need to use the system time, not the course time.

    # if both of those came back as none, or we haven't hit the 
    # Canvas API, use our own due date, as determined when the 
    # Assignment was instantiated (with the from the date from
    # the config object)

    # Use system due date before checking for canvas_assignment.
    if self.system_due_date is not None:
      close_time = self.system_due_date

    # If we found the assignment in Canvas, we can look for a lock date.
    elif hasattr(self, 'canvas_assignment') and self.canvas_assignment is not None:

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

    # If we STILL haven't found a due date by now, skip scheduling grading!!
    if not close_time:
      print(
        f'Could not find a due date or lock date for {self.name}, automatic grading will not be scheduled.'
      )
      scheduling_status['close_time'] = 'None'
      scheduling_status['action'] = 'None'
      
      # Exit early if no due date found!
      return scheduling_status

    # ============================================== #
    #     Done looking for due date (close time)     #
    # ============================================== #

    # pretty print the due date/close_time in the course timezone
    close_time_course_time = close_time   \
      .in_tz(self.course.course_timezone)

    scheduling_status['close_time'] = close_time_course_time.to_day_datetime_string()

    # Could potentially fall back to closing at course end date, but doesn't seem particularly helpful
    # elif self.course.get('end_at') is not None:
    #   close_time = parse(self.course['end_at'])

    # Make sure we don't have a job for this already, and then set it if it's valid

    # convert generator to list so we can iterate over it multiple times
    existing_jobs = list(self.course.cron.find_comment(f"Autograde {self.name}"))

    # Check to see if we found any preexisting jobs
    if (len(list(existing_jobs)) > 0):
      scheduling_status['action'] = f'{utils.color.PURPLE}updated{utils.color.END}'

      # if so, delete the previously scheduled jobs before setting a new command
      for job in existing_jobs:  
        self.course.cron.remove(job)

    # Otherwise just go ahead and set the job
    else:
      scheduling_status['action'] = f'{utils.color.DARKCYAN}created{utils.color.END}'

    # If we require manual grading, set the flag
    man_graded = ' -m' if self.manual else ''

    # Construct the grade command for cron to run
    grade_command = "eval `ssh-agent` && "                  + \
      "ssh-add /home/jupyter/.ssh/instructors && "          + \
      "ssh-add /home/jupyter/.ssh/students && "             + \
      f"bash -l -c \""                                      + \
      f"rudaux grade '{self.name}' --auto "                 + \
      f"--dir {self.course.working_directory}{man_graded} " + \
      f">> {self.course.working_directory}"                 + \
      f"/{close_time_course_time.format('YYYY-MM-DD-HHmm')}-autograde-{self.name}.log\""
      # Make sure we log the results!

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
      scheduling_status['action'] = 'failed'
      print(f'Automatic grading for {self.name} failed due to invalid cron job formatting:')
      print(new_autograde_job)
    
    return scheduling_status

  # This function is defunct. We are only mounting the ZFS fileserver 
  # to the grading server via a NFS mount, so we do not have access to 
  # ZFS commands. Instead, snapshots will be taken daily at 12:03am, 
  # and rudaux will look for the closest snapshot after the close date.
  # (see Assignment.collect())

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
    This essentially copies the notebooks to a new location.
    
    IMPORTANT:
    This also creates a submission in the gradebook on behalf of each student.
    If this is never done, then autograding doesn't record grades in the gradebook.
    """

    print(utils.banner(f"Collecting {self.name}"))

    try:
      student_ids = map(lambda stu: stu.get('id'), self.course.students)
    except Exception:
      sys.exit("No students found. Please run `course.get_students_from_canvas()` before collecting an assignment.")

    # If we're using a ZFS fileserver, we need to look for the relevant snapshots
    if self.course.zfs:
      # List all of the snapshots available and parse their dates
      snapshot_names = os.listdir(os.path.join(self.course.storage_path, '.zfs' 'snapshot'))

      snapshot_name = self._find_closest_snapshot(snapshot_names)

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
      # This works because our ZFS snapshots are recursive.
      if self.course.zfs and os.path.exists(os.path.join(student_path, '.zfs')):
        # Check that we're using ZFS
        assignment_path = os.path.join(
          student_path, 
          zfs_path,
          self.name
        )
      # otherwise just use the student's work directly
      else:
        assignment_path = os.path.join(
          student_path,
          self.name
        )

      submission_path = os.path.join(self.course.working_directory, 'submitted', student_id, self.name)
      # then copy the work into the submitted directory + student_id + assignment_name

      # Since we're JUST copying the current assignment, we can safely overwrite it
      try:
        shutil.rmtree(submission_path)
      # Doesn't matter if it doesn't exist though
      except:
        pass

      try:
        shutil.copytree(assignment_path, submission_path)
      # if no assignment for that student, fail
      #* NOTE: could also be due to incorrect directory structure.
      except FileNotFoundError:
        assignment_collected = False
        assignment_collection_status.append([student_id, f'{utils.color.RED}failure{utils.color.END}'])
      else: 
        assignment_collected = True
        assignment_collection_status.append([student_id, f'{utils.color.GREEN}success{utils.color.END}'])

      # **CRUCIALLY IMPORTANT**
      # If the assignment was successfully collected, create a submission in gradebook for the student.
      # If this is never done, then autograding doesn't
      # record grades in the gradebook.
      if assignment_collected: 
        try:
          self.course.nb_api.gradebook.add_submission(self.name, student_id)
          self.course.nb_api.gradebook.close()
        except Exception as e:
          self.course.nb_api.gradebook.close()
          raise e

    table = AsciiTable(assignment_collection_header + assignment_collection_status)
    table.title = 'Assignment Collection'
    print(table.table)

    # Do not exit if either of these operations fails. We wish to be able to
    # finish autograding even if we can't commit/push.

    try:
      utils.commit_repo(self.course.working_directory, f'Collected {self.name}')
    except Exception as e:
      print('\n')
      print('Error committing to your instructors repository:')
      print(e)
    else:
      print('\n')

    try:
      utils.push_repo(self.course.working_directory)
    except Exception as e:
      print('Error pushing your repository:')
      print(e)

    return self

  def grade(self):
    """
    Autograde an assignment via the nbgrader API.
    This runs `nbgrader autograde` within a docker container.
    """

    print(utils.banner(f"Autograding {self.name}"))

    try:
      res = subprocess.run(
        [
          "docker",
          "run",
          "--rm",
          "-u",
          "jupyter",
          "-v",
          f"/home/jupyter/{self.course.ins_repo_name}:/assignments/",
          self.course.grading_image,
          "autograde",
          self.name
        ],
        check=True
      )
    except subprocess.CalledProcessError:
      print(f"{utils.color.RED}Error autograding {self.name}{utils.color.END}")
    else: 
      if res.returncode != 0:
        print(f"{utils.color.RED}Unspecified error autograding {self.name}{utils.color.END}")
        print(res.stdout)
      else: 
        print(f"{utils.color.GREEN}Successfully autograded {self.name}{utils.color.END}")

    #===========================================#
    # Commit & Push Changes to Instructors Repo #
    #===========================================#
    
    # Do not exit if either of these operations fails. We wish to be able to
    # finish autograding even if we can't commit/push.

    try:
      utils.commit_repo(self.course.working_directory, f'Autograded {self.name}')
    except Exception as e:
      print('\n')
      print('Error committing to your instructors repository:')
      print(e)
    else:
      print('\n')

    try:
      utils.push_repo(self.course.working_directory)
    except Exception as e:
      print('Error pushing your repository:')
      print(e)

    return self

  def feedback(self):
    """
    Generate feedback reports for student assignments.  
    """

    print(utils.banner(f"Generating Feedback for {self.name}"))

    res = self.course.nb_api.feedback(assignment_id=self.name)

    if res.get('error') is not None:
      print(f"{utils.color.RED}Error generating feedback for {self.name}{utils.color.END}")
      print(res.get('error'))
    else: 
      print(f"{utils.color.GREEN}Successfully generated feedback for {self.name}{utils.color.END}")
    #===========================================#
    # Commit & Push Changes to Instructors Repo #
    #===========================================#

    # Do not exit if either of these operations fails. We wish to be able to
    # finish autograding even if we can't commit/push.

    try:
      utils.commit_repo(self.course.working_directory, f'Generated feedback for {self.name}')
    except Exception as e:
      print('\n')
      print('Error committing to your instructors repository:')
      print(e)
    else:
      print('\n')

    try:
      utils.push_repo(self.course.working_directory)
    except Exception as e:
      print('Error pushing your repository:')
      print(e)

    return self

  def submit(self):
    """
    Upload grades to Canvas.  
    """

    # Print banner
    print(utils.banner(f"Submitting {self.name}"))

    # Check that we have the canvas_assignment containing the assignment_id
    # ...and if we don't, get it!
    if not hasattr(self, 'canvas_assignment'):
      self.canvas_assignment = self._search_canvas_assignment()
    elif self.canvas_assignment is None:
      self.canvas_assignment = self._search_canvas_assignment()

    # Pull out the assignment ID
    assignment_id = self.canvas_assignment.get('id')

    # get the student IDs
    try:
      student_ids = map(lambda stu: stu.get('id'), self.course.students)
    except Exception:
      sys.exit("No students found. Please run `course.get_students_from_canvas()` before collecting an assignment.")

    grades = self._get_grades(student_ids)

    # Set up status reporting
    submission_header = [
      ['Student ID', 'Collection Status']
    ]
    submission_status = []

    # for each student
    for grade in grades:
      # upload their grade
      resp = requests.put(
        url=urlparse.urljoin(
          self.course.canvas_url, 
          f"/api/v1/courses/{self.course.course_id}/assignments/{assignment_id}/submissions/{grade.get('student_id')}"
        ),
        headers={
          "Authorization": f"Bearer {self.course.canvas_token}",
          "Accept": "application/json+canvas-string-ids"
        },
        json={
          "submission": {
            "posted_grade": grade.get('score')
          }
        }
      )

      if resp.status_code == 200:
        submission_status.append([grade.get('student_id'), f'{utils.color.GREEN}success{utils.color.END}'])
      else:
        submission_status.append([grade.get('student_id'), f'{utils.color.RED}failure{utils.color.END}'])

    table = AsciiTable(submission_header + submission_status)
    table.title = 'Assignment Submission'
    print(table.table)

    return self


  def _get_grades(self, student_ids: List[Union[str, int]]) -> Dict[str, Union[str, int]]:
    """Get the grade of an assignment for a list of students.
    
    :param student_ids: A list of your student IDs as strs or ints.
    :type student_ids: List[Union[str, int]]
    :return: A dictionary with each student's grade for the assignment.
    :rtype: Dict[str, Union[str, int]]
    """

    gradebook = self.course.nb_api.gradebook

    grades = []

    # wrap gradebook commands in a try/except to properly close gradebook
    # connection if an error occurs
    try:
      # get gradebook's copy of the assignment
      assignment = gradebook.find_assignment(self.name)

      # find grade for each student
      # Loop over each student in the database
      for student_id in student_ids:
        # Create a dictionary that will store information about this
        # student's submitted assignment

        score = {
          'student_id': student_id,
          'max_score': assignment.max_score
        }

        # Try to find the submission in the database. If it doesn't
        # exist, the `MissingEntry` exception will be raised, which
        # means the student didn't submit anything, so we assign them a
        # score of zero.
        try:
          submission = gradebook.find_submission(self.name, student_id)

        except nbgrader.api.MissingEntry:
          print(f"No submission found for {student_id}")
          score['timestamp'] = ''
          score['raw_score'] = 0.0
          score['late_submission_penalty'] = 0.0
          score['score'] = 0.0
        else:
          penalty = submission.late_submission_penalty
          score['timestamp'] = submission.timestamp
          score['raw_score'] = submission.score
          score['late_submission_penalty'] = penalty
          score['score'] = max(0.0, submission.score - penalty)

        for key in score:
          if score[key] is None:
            score[key] = ''
          if not isinstance(score[key], str):
            score[key] = str(score[key])
        grades.append(score)
    # unless we reach an error...
    except Exception as e:
      # Then close the connection
      gradebook.close()
      # and raise the exception
      raise e
    else:
      # otherwise
      gradebook.close()
      return grades

  def _find_closest_snapshot(
    self,
    snapshot_names: List[str],
    snapshot_prefix=r'^zfs-auto-snap_[a-z]+-',
    datetime_pattern='YYYY-MM-DD-HHmm'
  ):
    # If no snapshot prefix was specified, then we will 
    # parse the snapshot names directly as the datetimes

    snapshots = []

    if snapshot_prefix is None:
      for snap in snapshot_names:
        snapshots.append({
          'snapshot_name': snap,
          'unparsed_time': snap
        })
    else: 
     for snap in snapshot_names:
        snapshots.append({
          'snapshot_name': snap,
          'unparsed_time': re.sub(snapshot_prefix, '', snap)
        })

    for snap in snapshots:
      # parse the datetime strings into pendulum datetime objects
      snap['parsed_time'] = pendulum.from_format(
        snap['unparsed_time'], 
        datetime_pattern, 
        tz=self.course.system_timezone
      )

      # Calculate the difference in time between the due date and the snapshot time
      # This will return the number of seconds difference. 
      # Positive results mean that the snapshot was taken AFTER the due date
      # Negative results mean that the snapshot was taken BEFORE the due date
      snap['time_diff'] = self.system_due_date.diff(snap['parsed_time'], False).in_seconds()
    
    # Filter out snapshots that were taken before due date
    snapshots = list(
      filter(
        lambda snap: snap.get('time_diff', -1) > 0,
        snapshots
      )
    )

    # Find the index of the snapshot with the smallest time difference.
    # Since we've filtered out negative values, this will find the snapshot 
    # that was closest to the assignment due date, but not before.
    closest_snap_index = snapshots.index(min(snapshots, key=lambda snap: snap['time_diff']))

    # Pull out the closest snap given the index
    closest_snap = snapshots[closest_snap_index]

    # Return the name of the closest snapshot
    return closest_snap.get('snapshot_name')
# This will be called by cron and run after assignment closes

import requests
import os
import sys
import re
import shutil
import textwrap
from pathlib import Path
# Import my custom utiliy functions
import utils
# For parsing assignments from CSV
import pandas as pd
# For progress bar
from tqdm import tqdm
from weir import zfs
from github import Github
from git import Repo
# For setting up autograding
from crontab import CronTab
from assignment import Assignment
from dateutil.parser import parse
from terminaltables import AsciiTable, SingleTable
# For decoding base64-encoded files from GitHub API
from base64 import b64decode
# for urlencoding query strings to persist through user-redirect
from urllib.parse import urlsplit, urlunsplit, quote_plus
# Bring in nbgrader API
from nbgrader.apps import NbGraderAPI
# Don't reinvent the wheel! Use nbgrader's method for finding notebooks
from nbgrader import utils as nbutils
# Bring in Traitlet Configuration methods
from traitlets.config import Config
from traitlets.config.application import Application

#* All internal _methods() return an object
#* All external  methods() return self (are chainable), and mutate object state or initiate other side-effects

# Must be instantiated with a course ID
class Course:
  """
  Course object for manipulating an entire Canvas/JupyterHub/nbgrader course
  """

  def __init__(
    self, 
    course_dir=None,
    cron=False
  ):
    """
    :param course_dir: The directory your course. If none, defaults to current working directory. 
    :type course_dir: str

    :returns: A Course object for performing operations on an entire course at once.
    :rtype: Course
    """

    #=======================================#
    #     Working Directory & Git Sync      #
    #=======================================#

    # Set up the working directory. If no course_dir has been specified, then it
    # is assumed that this is the course directory. 
    self.working_directory = course_dir if course_dir is not None else os.getcwd()

    repo = Repo(self.working_directory)

    # Before we do ANYTHING, make sure our working directory is clean with no
    # untracked files! Unless we're running a cron job, in which case we don't
    # want to fail for an unexpected reason.
    if (repo.is_dirty() or repo.untracked_files) and (not cron):
      continue_with_dirty = input("Your repository is currently in a dirty state (modifications or untracked changes are present). We strongly suggest that you resolve these before proceeding. Continue? [y/n]: ")
      # if they didn't say no, exit
      if continue_with_dirty.lower() != 'y':
        sys.exit("Exiting...")

    # pull the latest copy of the repo
    utils.pull_repo(repo_dir=self.working_directory)

    # Make sure we're running our nbgrader commands within our instructors repo.
    # this will contain our gradebook database, our source directory, and other
    # things.
    config = Config()
    config.CourseDirectory.root = self.working_directory

    #=======================================#
    #              Load Config              #
    #=======================================#

    # Check for an nbgrader config file...
    if not os.path.exists(os.path.join(self.working_directory, 'nbgrader_config.py')):
      # if there isn't one, make sure there's at least a rudaux config file
      if not os.path.exists(os.path.join(self.working_directory, 'rudaux_config.py')):
        sys.exit(
          """
          You do not have nbgrader_config.py or rudaux_config.py in your current
          directory. We need at least one of these to set up your course
          parameters! You can specify a directory with the course_dir argument
          if you wish.
          """
        )

    # use the traitlets Application class directly to load nbgrader config file.
    # reference:
    # https://github.com/jupyter/nbgrader/blob/41f52873c690af716c796a6003d861e493d45fea/nbgrader/server_extensions/validate_assignment/handlers.py#L35-L37

    # ._load_config_files() returns a generator, so if the config is missing,
    # the generator will act similarly to an empty array

    # load rudaux_config if it exists, otherwise just bring in nbgrader_config.
    for rudaux_config in Application._load_config_files('rudaux_config', path=self.working_directory):
      config.merge(rudaux_config)
    
    for nbgrader_config in Application._load_config_files('nbgrader_config', path=self.working_directory):
      config.merge(nbgrader_config)

    #=======================================#
    #           Set Config Params           #
    #=======================================#

    # The try/except blocks below check to see if no c.Option.____ was specified
    # at all, because the first .get() returns None, and then we try to do
    # None.get(), which raises an AttributeError

    ## CANVAS PARAMS

    # Before we continue, make sure we have all of the necessary parameters.
    self.course_id = config.get('Canvas', {}).get('course_id')
    self.canvas_url = config.get('Canvas', {}).get('canvas_url')
    # The canvas url should have no trailing slash
    self.canvas_url = re.sub(r"/$", "", self.canvas_url)

    ## GITHUB PARAMS
    self.stu_repo_url = config.get('GitHub', {}).get('stu_repo_url')
    self.assignment_release_path = config.get('GitHub', {}).get('assignment_release_path')
    self.ins_repo_url = config.get('GitHub', {}).get('ins_repo_url')
    # subpath not currently supported
    # self.ins_dir_subpath = config.get('GitHub').get('ins_dir_subpath')
      
    ## JUPYTERHUB PARAMS

    self.hub_url = config.get('JupyterHub', {}).get('hub_url')
    # The hub url should have no trailing slash
    self.hub_url = re.sub(r"/$", "", self.hub_url)
    # Note hub_prefix, not base_url, to avoid any ambiguity
    self.hub_prefix = config.get('JupyterHub', {}).get('base_url')
    # If prefix was set, make sure it has no trailing slash, but a preceding
    # slash
    if self.hub_prefix is not None:
      self.hub_prefix = re.sub(r"/$", "", self.hub_prefix)
      if re.search(r"^/", self.hub_prefix) is None:
        self.hub_prefix = fr"/{self.hub_prefix}"

    ## COURSE PARAMS

    self.tmp_dir = config.get('Course', {}).get('tmp_dir')
    self.assignment_names = config.get('Course', {}).get('assignments')

    ## Repurpose the rest of the params for later batches
    ## (Hang onto them in case we need something)

    self.full_config = config

    #=======================================#
    #       Check For Required Params       #
    #=======================================#

    # Finally, before we continue, make sure all of our required parameters were
    # specified in the config file(s)
    required_params = {
      "c.Canvas.course_id": self.course_id,
      "c.Canvas.canvas_url": self.canvas_url,
      "c.GitHub.stu_repo_url": self.stu_repo_url,
      "c.GitHub.ins_repo_url": self.ins_repo_url,
      "c.JupyterHub.hub_url": self.hub_url,
      "c.Course.assignments": self.assignment_names
    }
    
    # If any are none...
    if None in required_params.values():
      # Figure out which ones are none and let the user know.
      for key, value in required_params.items():
        if value is None:
          print(f"\"{key}\" is missing.")
      sys.exit('Please make sure you have specified all required parameters in your config file.')

    #=======================================#
    #       Check For Optional Params       #
    #=======================================#

    # Now look for all of our optional parameters. If any are missing, let the
    # user know we'll be using the default. 
    optional_params = {
      "assignment_release_path": {
        "value": self.assignment_release_path,
        "default": 'materials',
        "config_name": "c.GitHub.assignment_release_path"
      },
      # "assignment_source_path": {
      #   "value": self.assignment_source_path,
      #   "default": "source",
      #   "config_name": "c.GitHub.assignment_source_path"
      # },
      "hub_prefix": {
        "value": self.hub_prefix,
        "default": "",
        "config_name": "c.JupyterHub.base_url"
      },
      "tmp_dir": {
        "value": self.tmp_dir,
        "default": os.path.join(Path.home(), 'tmp'),
        "config_name": "c.Course.tmp_dir"
      }
    }

    for key, param in optional_params.items():
      if param.get('value') is None:
        setattr(self, key, param.get('default'))
        print(f"\"{param.get('config_name')}\" is missing, using default parameter of \"{getattr(self, key)}\"")

    # check for tokens
    github_token_name = config.get('GitHub').get('github_token_name')
    token_names = config.get('GitHub').get('token_names')
        
    #=======================================#
    #           Set GitHub Token            #
    #=======================================#

    # If the config file specifies multiple tokens, use those
    if token_names is not None:
      # instantiate our token object as empty
      self.tokens = []
      # Then for each token specified...
      for token_name in token_names:
        # Create a token object with the domain and token necessary
        self.tokens.append({
          "domain": token_name.get('domain'),
          "token": self._get_token(token_name.get('token_name'))
        })
    # otherwise we'll use the same token for both github domains
    else:
      if github_token_name is None:
        self.github_tokens = None
        # Only look for PAT if it is specified by the user
        # This way we can prompt for user/pass if no token is available
          # if the user didn't specify a token_name, use 'GITHUB_PAT'
          # print("Searching for default GitHub token, GITHUB_PAT...")
          # github_token_name = 'GITHUB_PAT'
      else: 
        # get the single token we'll be using
        token = self._get_token(github_token_name)

        # Then specify that we're using the same token for each domain
        self.github_tokens = [
          {
            "domain": urlsplit(self.stu_repo_url).netloc,
            "token": token
          }, 
          {
            "domain": urlsplit(self.ins_repo_url).netloc,
            "token": token
          }
        ]

    #=======================================#
    #           Set Canvas Token            #
    #=======================================#

    canvas_token_name = config.get('Canvas').get('token_name')

    if canvas_token_name is None:
      print("Searching for default Canvas token, CANVAS_TOKEN...")
      canvas_token_name = 'CANVAS_TOKEN'

    self.canvas_token = self._get_token(canvas_token_name)

    #=======================================#
    #        Finalize Setting Params        #
    #=======================================#

    # set up the nbgrader api with our merged config files
    self.nb_api = NbGraderAPI(config=config)

    # assign init params to object
    # self.canvas_token = self._get_token(canvas_token_name)
    # self.course = self._get_course()
    self.cron = CronTab(user=True)

  # Get the canvas token from the environment
  def _get_token(self, token_name: str):
    """
    Get an API token from an environment variable.
    """
    try:
      token = os.environ[token_name]
      return token
    except KeyError as e:
      print(f"Could not find the environment variable \"{token_name}\".")
      raise e

  # def _get_course(self):
  #   """
  #   Get the basic course information from Canvas
  #   """
  #   resp = requests.get(
  #     url=f"{self.canvas_url}/api/v1/courses/{self.course_id}",
  #     headers={
  #       "Authorization": f"Bearer {self.canvas_token}",
  #       "Accept": "application/json+canvas-string-ids"
  #     }
  #   )

  #   # Make sure our request didn't fail silently
  #   resp.raise_for_status()
    
  #   # pull out the response JSON
  #   course = resp.json()
  #   return course

  def get_students(self):
    """
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    Get the student list for a course. 
    DEBUG NOTE: CURRENTLY INCLUDING TEACHERS TOO
    """

    print('Querying list of students...')
    # List all of the students in the course
    resp = requests.get(
      url=f"{self.canvas_url}/api/v1/courses/{self.course_id}/users",
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

    # Make sure our request didn't fail silently
    resp.raise_for_status()

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

  # def get_assignments_from_canvas(self):
  #   """
  #   Get all assignments for a course.
  #   """
  #   resp = requests.get(
  #     url=f"{self.canvas_url}/api/v1/courses/{self.course_id}/assignments",
  #     headers={
  #       "Authorization": f"Bearer {self.canvas_token}",
  #       "Accept": "application/json+canvas-string-ids"
  #     }
  #   )

  #   # Make sure our request didn't fail silently
  #   resp.raise_for_status()

  #   # pull out the response JSON
  #   canvas_assignments = resp.json()

  #   # Create an assignment object from each assignment
  #   # `canvas_assignments` is a list of objects (dicts) so `**` is like the object spread operator (`...` in JS)
  #   assignments = map(
  #     lambda assignment: Assignment(**assignment),
  #     canvas_assignments
  #   )
  #   self.assignments = assignments

  #   return self

  def assign(
    self, 
    assignments=None,
    overwrite=False,
  ):
    """Assign assignments for a course
    
    :param assignments: The name(s) of the assignment(s) you wish to assign, as a string or list of strings.
    :type assignments: str, List[str]
    :param overwrite: Whether or not you wish to overwrite preexisting directories
    :type overwrite: bool
    """

    # Make sure we've got assignments to assign
    if not assignments:
      print("No assignment in particular specified, assigning all assignments...")
      assignments_to_assign = self.assignments
    # otherwise, match the assignment(s) provided to the one in our config file
    else:
      # if just one assignment was specified...
      if isinstance(assignments, str):
        # find the assignments which match that name
        assignments_to_assign = list(filter(lambda assn: assn['name'] == assignments, self.assignments))
      elif isinstance(assignments, list):
        assignments_to_assign = []
        for assignment in assignments:
          match = list(filter(lambda assn: assn['name'] == assignments, self.assignments))
          assignments_to_assign.append(match)
      else: 
        sys.exit('Invalid argument supplied to `assign()`. Please specify a string or list of strings to assign.')

    # First things first, make the temporary directories
    ins_repo_dir = os.path.join(self.tmp_dir, 'instructors')
    stu_repo_dir = os.path.join(self.tmp_dir, 'students')

    #=======================================#
    #               Clone Repos             #
    #=======================================#

    try:
      utils.clone_repo(self.ins_repo_url, ins_repo_dir, overwrite, self.github_tokens)
    except Exception as e:
      print("There was an error cloning your instructors repository")
      raise e

    try:
      utils.clone_repo(self.stu_repo_url, stu_repo_dir, overwrite, self.github_tokens)
    except Exception as e:
      print("There was an error cloning your students repository")
      raise e

    #=======================================#
    #          Make Student Version         #
    #=======================================#

    # set up array to save assigned assignment names in. This will be so we can
    # record which assignments were assigned in the commit message. 
    assignment_names = []

    ### FOR LOOP - ASSIGN ASSIGNMENTS ###

    # For each assignment, assign!!
    print('Assigning assignments with nbgrader...')
    for assignment in tqdm(assignments_to_assign): 

      # Push the name to our names array for adding to the commit message.
      assignment_names.append(assignment.name)

      # assign the given assignment!
      self.nb_api.assign(assignment.name)

    ### END LOOP ###

    # set up directories to copy the assigned assignments to
    generated_assignment_dir = os.path.join(ins_repo_dir, 'release')
    student_assignment_dir = os.path.join(stu_repo_dir, self.assignment_release_path)

    if not os.path.exists(student_assignment_dir):
      os.makedirs(student_assignment_dir)

    #========================================#
    #   Move Assignments to Students Repo    #
    #========================================#

    utils.safely_delete(student_assignment_dir, overwrite)

    # Finally, copy to the directory, as we've removed any preexisting ones or
    # exited if we didn't want to
    shutil.copytree(generated_assignment_dir, student_assignment_dir)

    #===========================================#
    # Commit & Push Changes to Instructors Repo #
    #===========================================#

    utils.commit_repo(ins_repo_dir, assignment_names)
    utils.push_repo(ins_repo_dir)

    #========================================#
    # Commit & Push Changes to Students Repo #
    #========================================#

    utils.commit_repo(stu_repo_dir, assignment_names)
    utils.push_repo(stu_repo_dir)

    return self

  # def get_assignments_from_csv(self, path: str):
  #   """
  #   Bring in assignments from a CSV file. 
  #   CSV file should contain the following columns: 
    
  #   [required]
  #   - name (str): the name of the assignment
  #   - due_at (str): due date for the assignment
  #   - notebook_path (str): github URL at which the jupyter notebook lives
  #   - points_possible (int): the number of possible points

  #   [optional]
  #   - published (bool): whether the assignment should be published
  #   - description (str): a description of the assignment
  #   - unlock_at (str): a date at which the assignment becomes available
  #   - lock_at (str): date after the due date to which students can submit their assignment for partial credit

  #   :param path: Path to the CSV file. 
  #   """
  #   assignments = pd.read_csv(path)
  #   print(assignments)


  #! Figure out where to put this
  #? Do we really need the assignment class?
  #? What am I really doing here? More like generating the assignments
  #* The links are generated in Course.create_assignments_in_canvas()
  #* Perhaps this should be an assignment function
  #* Perhaps this should be in the constructor
  #? Can I better separate Course operations from Assignment operations?
  #! Continue working on this!!
  def generate_assignment_objects(self):
    """
    Generate assignment links for released assignments.
    """

    # give proper defaults to .get() to fail gracefully
    rudaux_exclusions = self.full_config.get('Course', {}).get('exclude', [])
    header = [self.full_config.get('IncludeHeaderFooter', {}).get('header'), []]
    footer = [self.full_config.get('IncludeHeaderFooter', {}).get('footer'), []]

    exclusions = rudaux_exclusions + header + footer

    # No subpaths implemented yet, so all source documents must live in
    # /instructors/source

    notebook_paths = nbutils.find_all_notebooks(self.working_directory)
    # create an empty list of assignments to push to
    assignments = []

    for notebook_path in notebook_paths:

      split_path = nbutils.full_split(notebook_path)
      filename = split_path[-1]
      assignment_name = split_path[-2]

      if filename not in exclusions:
        # add the assignment name, filename, and path to our list of assignments.
        assignment = Assignment(
          name=assignment_name, 
          path=notebook_path,
          ins_repo_url=self.ins_repo_url,
          github_tokens=self.github_tokens,
          canvas_url=self.canvas_url,
          course_id=self.course_id,
          canvas_token=self.canvas_token
        )
        assignments.append(assignment)

    # names = list(map(lambda assn: assn.name, assignments))
    # print(f"Found the following assignments: {sorted(names)}")
    self.assignments = assignments
    return self



  def init_nbgrader(self):
    """
    Enter information into the nbgrader gradebook database about the assignments and the students.
    """

    # nbgrader API docs: https://nbgrader.readthedocs.io/en/stable/api/gradebook.html#nbgrader.api.Gradebook
    # 1. Make sure we have all of the course assignments
    # 2. Make sure we have all of the course students
    # 3. Make sure we know where the nbgrader database is: nbgrader.api.Gradebook(db_url)
    # 4. Add assignments: `update_or_create_assignment(name, **kwargs)`
    # 5. Add students: `find_student(student_id)`, then `add_student(student_id, **kwargs)``

    return False

  def create_assignments_in_canvas(self, overwrite=False, stu_repo_url=None) -> 'None':
    """Create assignments for a course.

    :param overwrite: Whether or not you wish to overwrite preexisting assignments.
    :type overwrite: bool
    :param stu_repo_url: The URL of your student repository. If this was provided when instantiating the course, this parameter can be left out. 
    :type stu_repo_url: str
    """

    # Check for preexisting value
    stu_repo_url = stu_repo_url if stu_repo_url is not None else self.stu_repo_url

    # Construct launch url for nbgitpuller
    # First join our hub url, hub prefix, and launch url
    launch_url = f"{self.hub_url}{self.hub_prefix}/hub/lti/launch"
    # Then construct our nbgitpuller custom next parameter
    gitpuller_url = f"{self.hub_prefix}/hub/user-redirect/git-pull"
    # Finally, urlencode our repository and add that
    repo_encoded_url = quote_plus(stu_repo_url)

    # Finally glue this all together!! Now we just need to add the subpath for each assignment
    full_assignment_url = fr"{launch_url}?custom_next={gitpuller_url}%3Frepo%3Dhttps%3A%2F%2F{repo_encoded_url}%26subPath%3D"

    print("\nCreating assignments (preexisting assignments with the same name will be updated)...")

    # Initialize status table that we can push to as we go
    assignment_status = [
      ['Assignment', 'Action', 'Status', 'Message']
    ]

    for assignment in tqdm(self.assignments):
      # urlencode the assignment's subpath
      #! TO-DO: replace instructors/source path with student path
      #! Maybe we should be pulling from nbgrader_config.py for this!!!!
      subpath = quote_plus(assignment.path)
      # and join it to the previously constructed launch URL (hub + nbgitpuller language)
      full_path = full_assignment_url + subpath

      # FIRST check if an assignment with that name already exists.
      # Method mutates state, so no return *necessary* (but we have anyways)
      existing_assigmnents = assignment.search_canvas_assignment()

      # If we already have an assignment with this name in Canvas, update it!
      # We assigned to self, so could also check `if assignment.canvas_assignment`
      if existing_assigmnents['found'] > 0:
        existing_assignment_name = existing_assigmnents.get('assignment', {}).get('name')
        # First, check to see if the user specified overwriting:
        if not overwrite:
          overwrite_target_dir = input(
            f"{existing_assignment_name} already exists, would you like to overwrite? [y/n]: "
          )
          # if they said yes, remove the directory
          if overwrite_target_dir.lower() != 'y':
            sys.exit("Will not overwrite preexisting assignment.\nExiting...")
        # Then the assignment ID would be in the canvas_assignment dict
        assignment_id = assignment.canvas_assignment.get('id')
        result = assignment.update_canvas_assignment(
          assignment_id, 
          submission_types=['external_tool'],
          external_tool_tag_attributes={
            "url": full_path,
            "new_tab": True
            }
        )
        assignment_status.append([assignment.name, 'update', result.get('status'), result.get('message')])
      # otherwise create a new assignment
      else: 
        assignment.create_canvas_assignment(
          name=assignment.name, 
          submission_types=['external_tool'],
          external_tool_tag_attributes={
            "url": full_path,
            "new_tab": True
            }
        )
        assignment_status.append([assignment.name, 'create', result.get('status'), result.get('message')])

    ## Print status for reporting:
    table = SingleTable(assignment_status)
    table.title = 'Summary'
    print("\n")
    print(table.table)
    print("\n")
    notice = f"""
    {utils.color.BOLD}Notice:{utils.color.END} Unfortunately, the Canvas API currently has a limitation where it
    cannot link your external tool to the assignment. Therefore, as it stands,
    your launch requests are likely being sent without the LTI Consumer & Secret
    Keys. Therefore, you need to go into each assignment that was just created
    and link the tool by clicking "Find" under the "Submission" section, and
    then clicking the tool your institution created (such as "Jupyter"). This
    will change the URLs of your assignments. After that, re-run this command
    and the URLs will be re-updated.

    {utils.color.UNDERLINE}{self.canvas_url}/courses/{self.course_id}/assignments{utils.color.END}

    Unfortunately, there is no way to tell if the assignment is properly linked
    via the API, so you'll have to manually check that as well.
    """
    print(notice)
    return self


  # def schedule_grading(self):
  #   """
  #   Schedule assignment grading tasks in crontab. 
  #   It would probably make more sense to use `at` instead of `cron` except that:
  #     1. CentOS has `cron` by default, but not `at`
  #     2. The python CronTab module exists to make this process quite easy.
  #   """
  #   # If there is no 'lock at' time, then the due date is the time to grade.
  #   # Otherwise, grade at the 'lock at' time. This is to allow partial credit
  #   # for late assignments.
  #   # Reference: https://community.canvaslms.com/docs/DOC-10327-415273044
  #   for assignment in tqdm(self.assignments):
  #     self._schedule_assignment_grading(assignment)
  #   print('Grading scheduled!')

  # def _schedule_assignment_grading(self, assignment):
  #   job = self.cron.new(
  #     command=f"nbgrader collect {assignment.get('name')}",
  #     comment=f"Autograde {assignment.get('name')}"
  #   )

  #   if assignment.get('lock_at') is not None:
  #     close_time = parse(assignment['lock_at'])

  #   elif assignment.get('due_at') is not None:
  #     close_time = parse(assignment['due_at'])

  #   # Will need course info here
  #   elif self.course.get('end_at') is not None:
  #     close_time = parse(self.course['end_at'])

  #   else:
  #     close_time: None
  #     print(
  #       'Could not find an end date for your course in Canvas, automatic grading will not be scheduled.'
  #     )

  #   # * Make sure we don't have a job for this already, and then set it if it's valid
  #   existing_jobs = self.cron.find_command(f"nbgrader collect {assignment.get('name')}")

  #   # wonky syntax because find_command & find_comment return *generators*
  #   if (len(list(existing_jobs)) > 0) & job.is_valid():
  #     # Set job
  #     job.setall(close_time)
  #     self.cron.write()
  #   else:
  #     # delete previous command here
  #     # then set job
  #     job.setall(close_time)
  #     self.cron.write()

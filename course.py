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
# For setting up autograding
from crontab import CronTab
from assignment import Assignment
from dateutil.parser import parse
from terminaltables import AsciiTable, SingleTable
# For decoding base64-encoded files from GitHub API
from base64 import b64decode
# for urlencoding query strings to persist through user-redirect
from urllib.parse import urlsplit, urlunsplit, quote_plus
from nbgrader.apps import NbGraderAPI
from traitlets.config import Config
from traitlets.config.application import Application

#* All internal _methods() return an object
#* All external  methods() return self (are chainable), and mutate object state or initiate other side-effects

# Must be instantiated with a course ID
class Course:
  """
  Course object for manipulating an entire Canvas course
  """

  def __init__(
    self, 
    course_id: int, 
    canvas_url: str,
    hub_url: str, 
    stu_repo_url: None, 
    ins_repo_url: None, 
    canvas_token_name='CANVAS_TOKEN', 
    github_token_name='GITHUB_PAT',
    hub_prefix='',
  ):
    """
    :param course_id: The (numeric) Canvas Course ID. 
    :param canvas_url: Base URL to your Canvas deployment. Ex: "canvas.institution.edu".
    :param token_name: The name of your Canvas Token environment variable. Default: "CANVAS_TOKEN"
    :param hub_url: The launch url for your JupyterHub. Ex: "example.com/hub/lti/launch?custom_next=/hub/user-redirect/git-pull"
    :param stu_repo_url: The full url for the public github repository you will be pulling your students' notebooks from. Ex: "github.com/course/stu_repo_url"
    :param hub_prefix: If your jupyterhub installation has a prefix (c.JupyterHub.base_url), it must be included. Ex: "/jupyter"

    :returns: A Course object for performing operations on an entire course at once.
    :rtype: Course
    """

    # The hub prefix and urls should have no trailing slash
    hub_url = re.sub(r"/$", "", hub_url)
    canvas_url = re.sub(r"/$", "", canvas_url)
    hub_prefix = re.sub(r"/$", "", hub_prefix)
    # ...but the hub prefix should have a preceding slash
    if re.search(r"^/", hub_prefix) is None:
      hub_prefix = fr"/{hub_prefix}"

    # assign init params to object
    self.course_id = course_id
    self.canvas_url = canvas_url
    self.hub_url = hub_url
    self.hub_prefix = hub_prefix
    self.stu_repo_url = stu_repo_url
    self.ins_repo_url = ins_repo_url
    self.canvas_token_name = canvas_token_name
    self.github_token_name = github_token_name
    self.canvas_token = None
    self.github_pat = None
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
      print(f"You do not seem to have the '{token_name}' environment variable present:")
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

    if self.canvas_token is None:
      self.canvas_token = self._get_token(self.canvas_token_name)

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
    stu_repo_url=None, 
    ins_repo_url=None, 
    stu_assignment_path='assignments',
    assignments=[], 
    tmp_dir=os.path.join(Path.home(), 'tmp'),
    overwrite=False,
  ):
    """Assign assignments for a course

    :param stu_repo_url: The remote URL to your students' repository. You can also provide this during course instantiation, and it will not be required here.
    :type stu_repo_url: str
    :param ins_repo_url: The remote URL to your instructors' repository. You can also provide this during course instantiation, and it will not be required here.
    :type stu_repo_url: str
    :param assignments: An optional list of assignments
    :type assignments: list
    """

    #=======================================#
    #       Set up Parameters & Config      #
    #=======================================#

    # Check for preexisting self values
    stu_repo_url = stu_repo_url if stu_repo_url is not None else self.stu_repo_url
    ins_repo_url = ins_repo_url if ins_repo_url is not None else self.ins_repo_url

    if self.canvas_token is None:
      self.canvas_token = self._get_token(self.canvas_token_name)

    if self.github_pat is None:
      self.github_pat = self._get_token(self.github_token_name)

    # Double check for repo URLs, exit.
    if (stu_repo_url is None) or (ins_repo_url is None):
      sys.exit("You must supply the url to both your students and instructors repositories.")

    # Also check for assignment names that were passed in.
    if not assignments and not self.assignments:
      print(
      """
      No assignments detected. Please chain this command to a
      "get_assignments_from_*()" command in order to fetch assignment names or
      pass in assignment names manually via the "assignments" argument.
      """
      )

    # Now use object assignments if no new ones passed in
    # Note slightly different logic to denote empty list, rather than None
    if not assignments: 
      assignments = self.assignments

    # First things first, make the temporary directories
    ins_repo_dir = os.path.join(tmp_dir, 'instructors')
    stu_repo_dir = os.path.join(tmp_dir, 'students')

    #=======================================#
    #               Clone Repos             #
    #=======================================#

    try:
      utils.clone_repo(ins_repo_url, ins_repo_dir, overwrite, self.github_pat)
    except Exception as e:
      print("There was an error cloning your instructors repository")
      raise e

    try:
      utils.clone_repo(self.stu_repo_url, stu_repo_dir, overwrite, self.github_pat)
    except Exception as e:
      print("There was an error cloning your students repository")
      raise e

    #=======================================#
    #          Make Student Version         #
    #=======================================#

    # Make sure we're running our nbgrader commands within our instructors repo.
    # this will contain our gradebook database, our source directory, and other
    # things.
    custom_config = Config()
    custom_config.CourseDirectory.root = ins_repo_dir
    # use the traitlets Application class directly to load nbgrader config file.
    # reference:
    # https://github.com/jupyter/nbgrader/blob/41f52873c690af716c796a6003d861e493d45fea/nbgrader/server_extensions/validate_assignment/handlers.py#L35-L37
    for config in Application._load_config_files('nbgrader_config', path=ins_repo_dir):
      # merge it with our custom config
      custom_config.merge(config)

    # set up the nbgrader api with our merged config files
    nb_api = NbGraderAPI(config=custom_config)

    assignment_names = []

    ### FOR LOOP - ASSIGN ASSIGNMENTS ###

    # For each assignment, assign!!
    print('Assigning assignments with nbgrader...')
    print(assignments)
    for assignment in tqdm(assignments): 

      # quick check to see if we're passing in full assignment objects or just
      # the names of assignments
      if not assignment.name:
        name = assignment
      else: 
        name = assignment.name

      assignment_names.append(name)

      # assign the given assignment!
      nb_api.assign(name)

    ### END LOOP ###

    generated_assignment_dir = os.path.join(ins_repo_dir, 'release')
    student_assignment_dir = os.path.join(stu_repo_dir, stu_assignment_path)
    if not os.path.exists(student_assignment_dir):
      os.makedirs(student_assignment_dir)

    #========================================#
    #   Move Assignments to Students Repo    #
    #========================================#

    utils.safely_delete(student_assignment_dir, overwrite)

    # Finally, copy to the directory, as we've removed any preexisting ones or
    # exited if we didn't want to
    shutil.copytree(generated_assignment_dir, student_assignment_dir)

    #=======================================#
    #      Push Changes to Students Repo    #
    #=======================================#

    utils.push_repo(assignment_names, stu_repo_dir, self.stu_repo_url, self.github_pat)

    return None

  def get_assignments_from_github(
    self,
    repo_url: str,
    github_token_name=None,
    dir='source',
    exclude=[]
  ):
    """
    Get assignments from a GitHub repository which follows the nbgrader directory structure convention.

    :param repo_url: The name of the repository containing your assignments.
    :type repo_url: str
    :param exclude: Python nodebooks to exclude from assignment creation. A list of notebook names such as ['header.ipynb', footer.ipynb']
    :type exclude: list
    :param dir: The directory containing your assignments. Should be relative to repo root, defaults to 'source'.
    :type dir: str
    :param token_name: The name of the environment variable storing your GitHub Personal Access Token. Your PAT must have the "repos" permission.
    :type token_name: str
    """

    # Check for preexisting self values
    github_token_name = github_token_name if github_token_name is not None else self.github_token_name

    if self.canvas_token is None:
      self.canvas_token = self._get_token(self.canvas_token_name)

    if self.github_pat is None:
      self.github_pat = self._get_token(self.github_token_name)

    if repo_url.startswith('git@'):
      #! Note, there is logic for the git handling that could work with ssh repositories
      #! However, this requires parsing logic to keep both URLs and manage them separately
      sys.exit("Please supply the HTTPS url to your repository.")
      # ssh_url = repo_url
      # https_url = repo_url # parse logic would go here
    elif not repo_url.startswith('http'):
      sys.exit("Please specify the scheme for your urls (i.e. \"https://\")")
      
    # split user/repo url in to user & repo
    repo_info = self._generate_sections_of_url(repo_url)
    # Make sure we got back the expected result
    if len(repo_info) != 2:
      sys.exit(
        'We could not properly parse the URL you supplied. Make sure your URL points to a repository. Ex: https://github.com/jupyter/jupyter'
      )
    
    # Get the domain name for the github site
    gh_domain = urlsplit(repo_url).netloc
    # if we've gotten this far, check for the personal access token
    github_token = self._get_token(github_token_name)

    # strip any preceding `/` or `./` from path provided
    clean_dir = re.sub(r"^\.{0,1}/", "", dir)
    # strip any trailing `/` from path provided
    clean_dir = re.sub(r"/$", "", clean_dir)

    # Make sure the exclusion array has '.ipynb' file extensions
    clean_exclude = list(
      map(lambda name: name if re.search(r".ipynb$", name) else f"{name}.ipynb", exclude)
    )

    if "github.com" in gh_domain:
      # use default, api.github.com
      gh_api = Github(login_or_token=github_token)
    else:
      # use github enterprise endpoint
      gh_api = Github(base_url=f"https://{gh_domain}/api/v3", login_or_token=github_token)

    # get the git tree for our repository
    repo_tree = gh_api.get_user(repo_info[0]).get_repo(repo_info[1]).get_git_tree(
      "master", recursive=True
    ).tree
    # create an empty list of assignments to push to
    assignments = []

    # iterate through our tree
    print("\nSearching for jupyter notebooks...")
    for tree_element in tqdm(repo_tree):
      # If the tree element is in our path and is a jupyter notebook
      if tree_element.path.startswith(clean_dir) & tree_element.path.endswith('.ipynb'):
        # get the filename (excluding the path)
        file_search = re.search(r"[\w-]+\.ipynb$", tree_element.path)
        # and make sure we got a hit (redundant, but error-averse)
        if file_search is not None:
          # extract the first hit from re.search
          filename = file_search.group(0)
          # check that this isn't an excluded file
          if filename not in clean_exclude:
            # strip the file extension
            # name = re.sub(r".ipynb$", "", filename)

            # Get the folder containing the notebook
            split_path = os.path.split(tree_element.path)
            # split_path[1] will be the notebook
            # split_path[0] will be the rest of the path
            split_path = os.path.split(split_path[0])
            # Now, split_path[1] is the name of the folder containing the notebook
            # and split_path[0] is the rest of the upsteam path
            name = split_path[1]
            # Get the contents of the file
            # file = gh_api.get_user().get_repo(repo).get_contents(tree_element.path)
            # file_contents = b64decode(file.content)
            # https://pygithub.readthedocs.io/en/latest/github_objects/ContentFile.html#github.ContentFile.ContentFile

            # add the assignment name, filename, and path to our list of assignments.
            assignment = Assignment(
              name=name, 
              path=tree_element.path,
              github={
                "ins_repo_url": repo_url,
                "github_token_name": github_token_name
              },
              # Pass down necessary parameters
              canvas={
                "url": self.canvas_url,
                "course_id": self.course_id,
                "token_name": self.canvas_token_name
              }
            )
            assignments.append(assignment)

    # names = list(map(lambda assn: assn.name, assignments))
    # print(f"Found the following assignments: {sorted(names)}")
    self.assignments = assignments
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

    return(False)
    
  # courtesy of https://stackoverflow.com/questions/7894384/python-get-url-path-sections
  def _generate_sections_of_url(self, url: str):
    """Generate Sections of a URL's path
    
    :param url: The URL you wish to split
    :type url: str
    :return: A list of url paths
    :rtype: list
    """

    path = urlsplit(url).path
    sections = []
    temp = ""
    while (path != '/'):
      temp = os.path.split(path)
      if temp[0] == '':
        break
      path = temp[0]
      # Insert at the beginning to keep the proper url order
      sections.insert(0, temp[1])
    return sections

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
    # Then construct our nbgirpuller custom next parameter
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
        existing_assignment_name = existing_assigmnents.get('assignment').get('name')
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

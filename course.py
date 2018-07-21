# This will be called by cron and run after assignment closes

import requests
import os
import sys
import re
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
# For decoding base64-encoded files from GitHub API
from base64 import b64decode
# for urlencoding query strings to persist through user-redirect
from urllib.parse import urlsplit, urlunsplit, urljoin, quote_plus
# import nbgrader

#* All internal _methods() return an object
#* All external  methods() return self (are chainable), and mutate object state or initiate other side-effects


# Must be instantiated with a course ID
class Course:
  """
  Course object for manipulating an entire Canvas course
  """

  def __init__(
    self, course_id: int, canvas_url: str, hub_url: str, student_repo: str, token_name='CANVAS_TOKEN', hub_prefix=''
  ):
    """
    :param course_id: The (numeric) Canvas Course ID. 
    :param canvas_url: Base URL to your Canvas deployment. Ex: "canvas.institution.edu".
    :param token_name: The name of your Canvas Token environment variable. Default: "CANVAS_TOKEN"
    :param hub_url: The launch url for your JupyterHub. Ex: "example.com/hub/lti/launch?custom_next=/hub/user-redirect/git-pull"
    :param student_repo: The full url for the public github repository you will be pulling your students' notebooks from. Ex: "github.com/course/student_repo"
    :param hub_prefix: If your jupyterhub installation has a prefix (c.JupyterHub.base_url), it must be included. Ex: "/jupyter"

    :returns: A Course object for performing operations on an entire course at once.
    :rtype: Course
    """
    # clean urls
    # canvas_url = urlsplit(canvas_url)
    # hub_url = urlsplit(hub_url)
    # student_repo = urlsplit(student_repo)

    # For the hub prefix, it must have no trailing slash
    hub_prefix = re.sub(r"/$", "", hub_prefix)
    # ...but have a preceding slash
    if re.search(r"^/", hub_prefix) is None:
      hub_prefix = fr"/{hub_prefix}"

    # assign init params to object
    self.course_id = course_id
    self.canvas_url = canvas_url
    self.hub_url = hub_url
    self.hub_prefix = hub_prefix
    self.student_repo = student_repo
    self.token_name = token_name
    self.canvas_token = self._get_token(token_name)
    self.course = self._get_course()
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

  def _get_course(self):
    """
    Get the basic course information from Canvas
    """
    resp = requests.get(
      url=urljoin(self.canvas_url, f"/api/v1/courses/{self.course_id}"),
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )

    # Make sure our request didn't fail silently
    resp.raise_for_status()
    
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
      url=urljoin(self.canvas_url, f"/api/v1/courses/{self.course_id}/users"),
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

  def get_assignments_from_canvas(self):
    """
    Get all assignments for a course.
    """
    resp = requests.get(
      url=urljoin(self.canvas_url, f"/api/v1/courses/{self.course_id}/assignments"),
      headers={
        "Authorization": f"Bearer {self.canvas_token}",
        "Accept": "application/json+canvas-string-ids"
      }
    )

    # Make sure our request didn't fail silently
    resp.raise_for_status()

    # pull out the response JSON
    canvas_assignments = resp.json()

    # Create an assignment object from each assignment
    # `canvas_assignments` is a list of objects (dicts) so `**` is like the object spread operator (`...` in JS)
    assignments = map(
      lambda assignment: Assignment(**assignment),
      canvas_assignments
    )
    self.assignments = assignments

    return self

  def get_assignments_from_github(
    self,
    repo_url: str,
    pat_name='GITHUB_PAT',
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

    if repo_url.startswith('git@'):
      sys.exit("Please supply the HTTPS url to your repository.")
    elif not repo_url.startswith('http'):
      sys.exit("Please specify the scheme for your urls (i.e. \"https://\")")
      
    repo_info = self._generate_sections_of_url(repo_url)
    gh_domain = urlsplit(repo_url).netloc

    github_token = self._get_token(pat_name)

    # strip any preceding `/` or `./` from path provided
    clean_dir = re.sub(r"^\.{0,1}/", "", dir)
    # strip any trailing `/` from path provided
    clean_dir = re.sub(r"/$", "", clean_dir)

    # Make sure the exclusion array has '.ipynb' file extensions
    clean_exclude = list(
      map(lambda name: name if re.search(r".ipynb$", name) else f"{name}.ipynb", exclude)
    )

    if gh_domain == "github.com":
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
    print("Searching for jupyter notebooks...")
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
            #! TODO: Use the directory name as the assignment name, not the filename
            #! This matches nbgrader's directory structure
            # strip the file extension
            name = re.sub(r".ipynb$", "", filename)

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
                "pat_name": pat_name
              },
              # Pass down necessary parameters
              canvas={
                "url": self.canvas_url,
                "course_id": self.course_id,
                "token_name": self.token_name
              }
            )
            assignments.append(assignment)

    names = list(map(lambda assn: assn.name, assignments))
    print(f"Found the following assignments: {sorted(names)}")
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
    if len(sections) > 2:
      sys.exit(
        'We could not properly parse the URL you supplied. Make sure your URL points to a repository. Ex: https://github.com/jupyter/jupyter'
      )
    return sections

  def create_assignments_in_canvas(self) -> None:
    """Create assignments for a course.
    """

    # Construct launch url for nbgitpuller
    # First join our hub url, hub prefix, and launch url
    launch_url = urljoin(urljoin(self.hub_url, self.hub_prefix), '/hub/lti/launch')
    # Then construct our nbgirpuller custom next parameter
    gitpuller_url = urljoin(self.hub_prefix, "/hub/user-redirect/git-pull")
    # Finally, urlencode our repository and add that
    repo_encoded_url = quote_plus(self.student_repo)

    # Finally glue this all together!! Now we just need to add the subpath for each assignment
    full_assignment_url = fr"{launch_url}?custom_next={gitpuller_url}%3Frepo%3Dhttps%3A%2F%2F{repo_encoded_url}%26subPath%3D"

    print("Creating assignments (preexisting assignments with the same name will be updated)...")

    for assignment in tqdm(self.assignments):
      # urlencode the assignment's subpath
      subpath = quote_plus(assignment.path)
      # and join it to the previously constructed launch URL (hub + nbgitpuller language)
      full_path = full_assignment_url + subpath

      # FIRST check if an assignment with that name already exists.
      # Method mutates state, so no return necessary, but done for clarity
      assignment = assignment.search_canvas_assignment()

      # If we already have an assignment with this name in Canvas, update it!
      if assignment.canvas_assignment:
        # Then the assignment ID would be in the canvas_assignment dict
        assignment_id = assignment.canvas_assignment.get('id')
        assignment.update_canvas_assignment(
          assignment_id, 
          external_tool_tag_attributes={
            "url": full_path,
            "new_tab": True
            }
        )
      # otherwise create a new assignment
      else: 
        assignment.create_canvas_assignment(
          name=assignment.name, 
          external_tool_tag_attributes={
            "url": full_path,
            "new_tab": True
            }
        )

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

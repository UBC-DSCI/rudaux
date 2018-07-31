""" Utility functions for Rudaux """

import os
import re
import sys
import shutil
import urllib.parse as urlparse
from github import Github
from git import Repo
from typing import List

# The functions here are not attached to a class as per advice:
# https://stackoverflow.com/questions/19620498/how-to-create-an-utility-class-correctly


def safely_delete(path: str, overwrite: bool) -> 'None':
  """Safely delete a directory
  
  :param path: The directory to delete.
  :type path: str
  :param overwrite: A boolean override to bypass prompt.
  :type overwrite: bool
  """

  # If the path exists...
  if os.path.exists(path):
    # If we allowed for overwriting, just go ahead and remove the directory
    if overwrite:
      shutil.rmtree(path)
    # Otherwise, ask first
    else:
      overwrite_target_dir = input(
        f"{path} is not empty, would you like to overwrite? [y/n]: "
      )
      # if they said yes, remove the directory
      if overwrite_target_dir.lower() == 'y':
        shutil.rmtree(path)
      # otherwise, exit
      else:
        sys.exit("Will not overwrite specified directory.\nExiting...")


def clone_repo(
  repo_url: str, target_dir: str, overwrite: bool, github_pat=None
) -> 'None':
  """Clone a repository
  
  :param repo_url: The ssh or https url for the repository you wish to clone.
  :type repo_url: str
  :param target_dir: The directory you wish to clone your repository to.
  :type target_dir: str
  """

  safely_delete(target_dir, overwrite)

  # Finally, make the directory, as we've removed any preexisting ones or
  # exited if we didn't want to
  os.makedirs(target_dir)

  split_url = urlparse.urlsplit(repo_url)

  print(f"Cloning from {repo_url}...")
  # If you use `urlparse` on a github ssh string, the entire result gets put
  # in 'path', leaving 'netloc' an empty string. We can check for that.
  if not split_url.netloc:
    # SO, if using ssh, go ahead and clone.
    print('SSH URL detected, assuming SSH keys are accounted for...')
    Repo.clone_from(repo_url, target_dir)

  # Otherwise, we can get the github username from the API and use username/PAT
  # combo to authenticate.
  elif github_pat is not None:
    github_username = find_github_username(repo_url, github_pat)
    repo_url_auth = f"https://{github_username}:{github_pat}@{split_url.netloc}{split_url.path}.git"
  # Otherwise we can just prompt for user/pass
  else:
    repo_url_auth = f"https://{split_url.netloc}{split_url.path}.git"
    Repo.clone_from(repo_url_auth, target_dir)

  return None


def pull_repo(repo_dir: str, branch='master', remote='origin') -> 'None':
  """Pull a repository

  :return: None
  :rtype: None
  """
  repo = Repo(repo_dir)
  repo.git.pull(remote, branch)


def commit_repo(
  repo_dir: str,
  names: List[str],
):
  """Commit all changes to a specified repository.
  
  :param repo_dir: The location of the repository on the disk you wish to commit changes to and push to its remote.
  :type repo_dir: str
  :param names: The names of the assignments you are pushing
  :type names: list
  :returns: Nothing, side effects performed.
  :rtype: None
  """

  # instantiate our repository
  repo = Repo(repo_dir)
  # add all changes
  repo.git.add("--all")  # or A=True
  # get repo status with frontmatter removed. We can use regex for this
  # because the output will be consistent as we are always adding ALL changes
  repo_status = re.sub(r"(.*\n)+.+to unstage\)", "", repo.git.status())
  # Strip the whitespace at the beginning of the lines
  whitespace = re.compile(r"^\s*", re.MULTILINE)
  repo_status = re.sub(whitespace, "", repo_status)
  # And strip any preceding or trailing whitespace
  print(repo_status.strip())
  print(f"assignment names: {' '.join(names)}")
  repo.git.commit("-m", f"Assigning {' '.join(names)}")


def push_repo(
  repo_dir: str,
  # repo_url: str,
  # github_pat=None,
  branch='master',
  remote='origin',
) -> 'None':
  """Commit changes and push a specific repository to its remote.
  
  :param repo_dir: The location of the repository on the disk you wish to commit changes to and push to its remote.
  :type repo_dir: str
  :param repo_url: The remote url of the location you're pushing to.
  :type repo_url: str
  :param branch: The branch you wish to commit changes to.
  :type branch: str
  :param remote: The remote you with to push changes to.
  :type remote: str
  :returns: Nothing, side effects performed.
  :rtype: None
  """

  # instantiate our repository
  repo = Repo(repo_dir)
  print(f"Pushing changes on {branch} to {remote}...")
  repo.git.push(remote, branch)

  # split_url = urlparse.urlsplit(repo_url)
  # if not split_url.netloc:
  #   # If using ssh, go ahead and clone.
  #   print('SSH URL detected, assuming SSH keys are accounted for.')
  #   print(f"Pushing changes on {branch} to {remote}...")
  #   repo.git.push(remote, branch)
  # # Otherwise, we can get the github username from the API and use username/PAT
  # # combo to authenticate.
  # elif github_pat is not None:
  #   github_username = find_github_username(repo_url, github_pat)
  #   repo_url_auth = f"https://{github_username}:{github_pat}@{split_url.netloc}{split_url.path}.git"
  #   print(f"Pushing changes on {branch} to {repo_url}...")
  #   repo.git.push(repo_url_auth, branch)
  # # Otherwise we can just prompt for user/pass
  # else:
  #   print(f"Pushing changes on {branch} to {repo_url}...")
  #   repo_url_auth = f"https://{split_url.netloc}{split_url.path}.git"
  #   repo.git.push(repo_url_auth, branch)

  return None


def find_github_username(url: str, pat: str) -> 'str':
  """Find a github username through the github api.
  
  :param url: Any github or github enterprise url.
  :type url: str
  :param pat: A personal access token for the account in question.
  :type pat: str
  :return: The username of the PAT holder.
  :rtype: str
  """

  split_url = urlparse.urlsplit(url)
  # If we're trying to clone from github.com...
  if split_url.netloc == 'github.com':
    # Github() default is api.github.com
    github_username = Github(pat).get_user().login
  # Otherwise, use the GHE Domain
  else:
    github_username = Github(
      base_url=urlparse.urljoin(url, "/api/v3"), login_or_token=pat
    ).get_user().login

  return github_username


class color:
  PURPLE = '\033[95m'
  CYAN = '\033[96m'
  DARKCYAN = '\033[36m'
  BLUE = '\033[94m'
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  BOLD = '\033[1m'
  UNDERLINE = '\033[4m'
  END = '\033[0m'


# courtesy of https://stackoverflow.com/questions/7894384/python-get-url-path-sections
def _generate_sections_of_url(url: str):
  """Generate Sections of a URL's path
  
  :param url: The URL you wish to split
  :type url: str
  :return: A list of url paths
  :rtype: list
  """

  path = urlparse.urlsplit(url).path
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
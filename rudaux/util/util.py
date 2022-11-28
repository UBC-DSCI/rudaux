import prefect
import os
import pwd
import grp
from prefect import get_run_logger
import logging


# --------------------------------------------------------------------------------------------------
def get_logger():
    # return prefect.context.get("logger")
    # return get_run_logger()
    return logging.getLogger("my-logger")


# --------------------------------------------------------------------------------------------------
def recursive_chown(path, user, group):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for di in dirs:
            os.chown(os.path.join(root, di), uid, gid)
        for fi in files:
            os.chown(os.path.join(root, fi), uid, gid)


# --------------------------------------------------------------------------------------------------
def clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())


# ----------------------------------------------------------------------------------------------------------
def grader_account_name(group_name: str, assignment_name: str, username: str):
    return clean_jhub_uname(group_name) + clean_jhub_uname(assignment_name) + clean_jhub_uname(username)


# ----------------------------------------------------------------------------------------------------------
class State:
    skip: bool = False
    re_run: bool = False


# ----------------------------------------------------------------------------------------------------------
def signal(func):
    def inner(state: State, *args, **kwargs):

        if state.skip:
            return
        else:
            output = func(state=state, *args, **kwargs)
            return output

    return inner

# ----------------------------------------------------------------------------------------------------------

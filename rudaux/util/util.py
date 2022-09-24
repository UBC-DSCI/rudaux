import prefect
import os
import pwd
import grp
from prefect import get_run_logger
import logging


def get_logger():
    # return prefect.context.get("logger")
    # return get_run_logger()
    return logging.getLogger("my-logger")


def recursive_chown(path, user, group):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for di in dirs:
            os.chown(os.path.join(root, di), uid, gid)
        for fi in files:
            os.chown(os.path.join(root, fi), uid, gid)

import prefect
import os
import pwd
import grp

def get_logger():
    return prefect.context.get("logger")

def recursive_chown(path, user, group):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for di in dirs:
          os.chown(os.path.join(root, di), uid, gid)
        for fi in files:
          os.chown(os.path.join(root, fi), uid, gid)



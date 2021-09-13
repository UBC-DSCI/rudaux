import prefect
import os

def get_logger():
    return prefect.context.get("logger")

def recursive_chown(path, uid):
    os.chown(path, uid, uid)
    for root, dirs, files in os.walk(path):
        for di in dirs:
          os.chown(os.path.join(root, di), uid, uid)
        for fi in files:
          os.chown(os.path.join(root, fi), uid, uid)

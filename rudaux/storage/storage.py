from traitlets.config.configurable import Configurable

# TODO fix the API here to conform to remote_zfs.py
class Storage(Configurable):

    def __init__(self):
        pass

    def close(self):
        raise NotImplementedError

    def get_snapshots(self):
        raise NotImplementedError

    def take_snapshot(self, snapshot, student=None, assignment=None):
        raise NotImplementedError

    def read(self, student, storage_relative_path, local_relative_path, snapshot=None):
        raise NotImplementedError

    def write(self, student, local_relative_path, storage_relative_path):
        raise NotImplementedError

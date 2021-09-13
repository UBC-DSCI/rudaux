from traitlets.config.configurable import Configurable

class Storage(Configurable):

    def __init__(self):
        pass

    def get_snapshots(self):
        raise NotImplementedError

    def take_snapshot(self, snapshot, student, relative_path):
        raise NotImplementedError

    def read(self, snapshot, student, relative_path):
        raise NotImplementedError

    def write(self, student, relative_path, stream):
        raise NotImplementedError

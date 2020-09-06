from traitlets.config.configurable import Configurable
from traitlets import Int, Float, Unicode, Bool

class Person:

    def __init__(self, canvasdict):
        self.__dict__.update(canvasdict)
        self.submissions = []

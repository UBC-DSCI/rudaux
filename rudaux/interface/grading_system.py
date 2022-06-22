from traitlets.config.configurable import Configurable

class GraderAPI(Configurable):
    def __init__(self):
        pass

    def initialize(self):
        raise NotImplementedError

    def generate_solution(self):
        raise NotImplementedError

    def generate_feedback(self):
        raise NotImplementedError

    def get_needs_manual_grading(self):
        raise NotImplementedError

    def autograde(self):
        raise NotImplementedError



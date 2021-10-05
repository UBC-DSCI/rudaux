from traitlets.config.configurable import Configurable

class LMSAPI(Configurable):

    def __init__(self):
        pass

    def get_course_info(self):
        raise NotImplementedError

    def get_people(self, enrollment_type):
        raise NotImplementedError

    def get_groups(self):
        raise NotImplementedError

    def get_assignments(self):
        raise NotImplementedError

    def get_submissions(self, assignment):
        raise NotImplementedError

    def update_grade(self, submission):
        raise NotImplementedError

    def update_extension(self, assignment, extension):
        raise NotImplementedError

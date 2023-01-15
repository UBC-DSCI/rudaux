import fwirl
import pendulum as plm

from fwirl.resource import Resource
from fwirl.worker import GraphWorker

from rudaux.flows import load_settings
from rudaux.model import Settings
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system


# ------------------------------------------------------------------------------------------------
# Workers
# ------------------------------------------------------------------------------------------------
class SubmissionBuilder(GraphWorker):

    def __init__(self, watched_assets):
        self.watched_assets = watched_assets
        super().__init__(watched_assets)

    def restructure(self, graph):
        pass


# ------------------------------------------------------------------------------------------------
class GraderBuilder(GraphWorker):

    def __init__(self, watched_assets):
        self.watched_assets = watched_assets
        super().__init__(watched_assets)

    def restructure(self, graph):
        pass

import fwirl
import pendulum as plm

from fwirl.resource import Resource
from fwirl.worker import GraphWorker
from rudaux.flows import load_settings
from rudaux.model import Settings
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system
from rudaux.fwirl_components.assets import AssignmentsListAsset, StudentsListAsset, \
    GradersListAsset, DeadlineAsset


# ------------------------------------------------------------------------------------------------
# Workers
# ------------------------------------------------------------------------------------------------
class SubmissionBuilder(GraphWorker):

    def __init__(self, assignments_list_asset, students_list_asset, lms_resource):
        self.assignments_list_asset = assignments_list_asset
        self.students_list_asset = students_list_asset
        self.lms_resource = lms_resource
        super().__init__([assignments_list_asset, students_list_asset])

    def restructure(self, graph):
        expected_assets = dict()
        for assignment_id, assignment in self.assignments_list_asset.get().items():
            for student_id, student in self.students_list_asset.get().items():
                deadline_asset = DeadlineAsset(
                    key=f"Deadline_A{assignment_id}_S{student_id}",
                    dependencies=[],
                    lms_resource=self.lms_resource,
                    student=student,
                    assignment=assignment
                )
                expected_assets[f"A{assignment_id}_S{student_id}"] = deadline_asset

        assets_to_add = expected_assets.copy()
        assets_to_remove = dict()
        for asset in graph:
            graph_asset_identifier = f"A{asset.group}_S{asset.subgroup}"
            if graph_asset_identifier in expected_assets:
                # if the asset is expected to remain
                del assets_to_add[graph_asset_identifier]
            else:
                # if the asset is expected to be removed
                assets_to_remove[graph_asset_identifier] = asset

        graph.remove_asset(list(assets_to_remove.values()))
        graph.add_assets(list(assets_to_add.values()))


# ------------------------------------------------------------------------------------------------
class GraderBuilder(GraphWorker):

    def __init__(self, watched_assets):
        self.watched_assets = watched_assets
        super().__init__(watched_assets)

    def restructure(self, graph):
        pass

import fwirl
import pendulum as plm

from fwirl.resource import Resource
from fwirl.worker import GraphWorker
from rudaux.flows import load_settings
from rudaux.model import Settings
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system
from rudaux.fwirl_components.assets import AssignmentsListAsset, StudentsListAsset, \
    GradersListAsset, DeadlineAsset, SubmissionRawAsset, SubmissionCleanedAsset, SubmissionAutoGradedAsset, \
    SubmissionManuallyGradedAsset, GeneratedFeedbackAsset, UploadedGradeAsset, ReturnedSolutionAsset, \
    SubmittedFractionAsset


# ------------------------------------------------------------------------------------------------
# Workers
# ------------------------------------------------------------------------------------------------
class SubmissionBuilder(GraphWorker):

    def __init__(self, assignments_list_asset, students_list_asset,
                 lms_resource, submission_system_resource):
        self.assignments_list_asset = assignments_list_asset
        self.students_list_asset = students_list_asset
        self.lms_resource = lms_resource
        self.submission_system_resource = submission_system_resource
        super().__init__([assignments_list_asset, students_list_asset])

    async def restructure(self, graph):
        expected_assets = dict()
        for assignment_id, assignment in (await self.assignments_list_asset.get()).items():

            # submitted_fraction_asset = SubmittedFractionAsset(
            #     key=f"SubmittedFraction_A{assignment_id}",
            #     dependencies=[],
            #     resources=[self.submission_system_resource],
            #     group=assignment_id,
            #     subgroup=0)

            for student_id, student in (await self.students_list_asset.get()).items():

                # ----------------------------------------------------------------
                deadline_asset = DeadlineAsset(
                    key=f"Deadline_A{assignment_id}_S{student_id}",
                    dependencies=[],
                    lms_resource=self.lms_resource,
                    student=student,
                    assignment=assignment
                )
                # # ----------------------------------------------------------------
                # submission_raw_asset = SubmissionRawAsset(
                #         key=f"SubmissionRaw_A{assignment_id}_S{student_id}",
                #         dependencies=[deadline_asset],
                #         resources=[self.submission_system_resource],
                #         group=assignment_id,
                #         subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # submission_cleaned_asset = SubmissionCleanedAsset(
                #     key=f"SubmissionCleaned_A{assignment_id}_S{student_id}",
                #     dependencies=[submission_raw_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # submission_auto_graded_asset = SubmissionAutoGradedAsset(
                #     key=f"SubmissionAutoGraded_A{assignment_id}_S{student_id}",
                #     dependencies=[submission_cleaned_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # submission_manually_graded_asset = SubmissionManuallyGradedAsset(
                #     key=f"SubmissionManuallyGraded_A{assignment_id}_S{student_id}",
                #     dependencies=[submission_auto_graded_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # generated_feedback_asset = GeneratedFeedbackAsset(
                #     key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
                #     dependencies=[submission_manually_graded_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # uploaded_grade_asset = UploadedGradeAsset(
                #     key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
                #     dependencies=[submission_manually_graded_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------
                # returned_solution_asset = ReturnedSolutionAsset(
                #     key=f"ReturnedSolution_A{assignment_id}_S{student_id}",
                #     dependencies=[deadline_asset, submitted_fraction_asset],
                #     resources=None,
                #     group=assignment_id,
                #     subgroup=student_id
                # )
                # # ----------------------------------------------------------------

                expected_assets[f"A{assignment_id}_S{student_id}"] = deadline_asset

        assets_to_add = expected_assets.copy()
        assets_to_remove = dict()
        for asset in graph.graph:
            graph_asset_identifier = f"A{asset.group}_S{asset.subgroup}"
            if graph_asset_identifier in expected_assets:
                # if the asset is expected to remain
                del assets_to_add[graph_asset_identifier]
            else:
                # if the asset is expected to be removed
                assets_to_remove[graph_asset_identifier] = asset

        graph.remove_assets(list(assets_to_remove.values()))
        graph.add_assets(list(assets_to_add.values()))


# ------------------------------------------------------------------------------------------------
class GraderBuilder(GraphWorker):

    def __init__(self, watched_assets):
        self.watched_assets = watched_assets
        super().__init__(watched_assets)

    def restructure(self, graph):
        pass

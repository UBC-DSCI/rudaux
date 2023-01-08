import fwirl
import pendulum as plm

from fwirl.resource import Resource
from fwirl.worker import GraphWorker

n_students = 10
n_assignments = 5
n_graders = 3

list_of_assignments = [{'id': i, 'name': f'student_{i}'} for i in range(n_assignments)]
list_of_students = [{'id': i, 'name': f'student_{i}'} for i in range(n_students)]
list_of_graders = [{'id': i, 'name': f'student_{i}'} for i in range(n_graders)]


# ------------------------------------------------------------------------------------------------
class AssignmentsListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class StudentsListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class GradersListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class DeadlineAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class SubmissionRawAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class SubmissionCleanedAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class SubmissionAutoGradedAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class SubmissionManuallyGradedAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class GeneratedFeedbackAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class ReturnedFeedbackAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class UploadedGradeAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class SubmittedFractionAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class ReturnedSolutionAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
class GraderAccountAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable


# ------------------------------------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------------------------------------
class LMSResource(Resource):
    def __init__(self, key):
        self.hash = hash(key)
        self.key = key
        super().__init__(key)

        self.list_of_students = list_of_students
        self.list_of_assignments = list_of_assignments
        self.list_of_graders = list_of_graders

    def init(self):
        pass

    def close(self):
        pass


# ------------------------------------------------------------------------------------------------
class GradingSystemResource(Resource):
    def __init__(self, key):
        self.hash = hash(key)
        self.key = key
        super().__init__(key)

        self.list_of_students = list_of_students
        self.list_of_assignments = list_of_assignments
        self.list_of_graders = list_of_graders

    def init(self):
        pass

    def close(self):
        pass


# ------------------------------------------------------------------------------------------------
class SubmissionSystemResource(Resource):
    def __init__(self, key):
        self.hash = hash(key)
        self.key = key
        super().__init__(key)

        self.list_of_students = list_of_students
        self.list_of_assignments = list_of_assignments
        self.list_of_graders = list_of_graders

    def init(self):
        pass

    def close(self):
        pass


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


# ------------------------------------------------------------------------------------------------


if __name__ == '__main__':

    g = fwirl.AssetGraph("rudaux_graph")

    grader_account_assets = dict()
    deadline_assets = dict()
    submission_raw_assets = dict()
    submission_cleaned_assets = dict()
    submission_auto_graded_assets = dict()
    submission_manually_graded_assets = dict()
    generated_feedback_assets = dict()
    returned_feedback_assets = dict()
    uploaded_grade_assets = dict()
    returned_solution_assets = dict()

    lms_resource = LMSResource(key=0)
    grading_system_resource = GradingSystemResource(key=0)
    submission_system_resource = SubmissionSystemResource(key=0)

    assignments_list_asset = AssignmentsListAsset(
        key=f"AssignmentsList",
        dependencies=[],
        resources=None,
        group=0,
        subgroup=0)

    students_list_asset = StudentsListAsset(
        key=f"StudentsListAsset",
        dependencies=[],
        resources=None,
        group=0,
        subgroup=0)

    graders_list_asset = GradersListAsset(
        key=f"GradersListAsset",
        dependencies=[],
        resources=[grading_system_resource],
        group=0,
        subgroup=0)

    SubmissionBuilder(watched_assets=[assignments_list_asset, students_list_asset, graders_list_asset])
    GraderBuilder(watched_assets=[students_list_asset, graders_list_asset])

    for assignment in list_of_assignments:
        assignment_id = assignment['id']

        # -----------------------------------------------------------------------------
        # dependencies: uploaded_grade_asset -> submission_manually_graded_asset
        submitted_fraction_asset = SubmittedFractionAsset(
            key=f"SubmittedFraction_A{assignment_id}",
            dependencies=[],
            resources=[submission_system_resource],
            group=assignment_id,
            subgroup=0)

        uploaded_grade_assets[f"A{assignment_id}"] = submitted_fraction_asset
        # -----------------------------------------------------------------------------

        for grader in list_of_graders:
            grader_id = grader['id']

            # dependencies: grader_account_asset ->
            grader_account_asset = GraderAccountAsset(
                key=f"GraderAccount_A{assignment_id}",
                dependencies=[],
                resources=None,
                group=assignment_id,
                subgroup=grader_id)

            grader_account_assets[f"A{assignment_id}_G{grader_id}"] = grader_account_asset

        # -----------------------------------------------------------------------------

        for student in list_of_students:
            student_id = student['id']

            # -----------------------------------------------------------------------------
            # dependencies: deadline_asset -> []
            deadline_asset = DeadlineAsset(
                key=f"Deadline_A{assignment_id}_S{student_id}",
                dependencies=[],
                resources=[lms_resource],
                group=assignment_id,
                subgroup=student_id)

            deadline_assets[f"A{assignment_id}_S{student_id}"] = deadline_asset

            # -----------------------------------------------------------------------------
            # dependencies: submission_asset -> deadline_asset
            submission_raw_asset = SubmissionRawAsset(
                key=f"SubmissionRaw_A{assignment_id}_S{student_id}",
                dependencies=[deadline_asset],
                resources=[submission_system_resource],
                group=assignment_id,
                subgroup=student_id)

            submission_raw_assets[f"A{assignment_id}_S{student_id}"] = submission_raw_asset

            # -----------------------------------------------------------------------------
            # dependencies: submission_cleaned_asset -> submission_asset
            submission_cleaned_asset = SubmissionCleanedAsset(
                key=f"SubmissionCleaned_A{assignment_id}_S{student_id}",
                dependencies=[submission_raw_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            submission_cleaned_assets[f"A{assignment_id}_S{student_id}"] = submission_cleaned_asset

            # -----------------------------------------------------------------------------
            # dependencies: submission_auto_graded_asset -> submission_cleaned_asset
            submission_auto_graded_asset = SubmissionAutoGradedAsset(
                key=f"SubmissionAutoGraded_A{assignment_id}_S{student_id}",
                dependencies=[submission_cleaned_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            submission_auto_graded_assets[f"A{assignment_id}_S{student_id}"] = submission_auto_graded_asset

            # -----------------------------------------------------------------------------
            # dependencies: submission_manually_graded_asset -> submission_auto_graded_asset
            submission_manually_graded_asset = SubmissionManuallyGradedAsset(
                key=f"SubmissionManuallyGraded_A{assignment_id}_S{student_id}",
                dependencies=[submission_auto_graded_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            submission_manually_graded_assets[f"A{assignment_id}_S{student_id}"] = submission_manually_graded_asset

            # -----------------------------------------------------------------------------
            # dependencies: generated_feedback_asset -> submission_manually_graded_asset
            generated_feedback_asset = GeneratedFeedbackAsset(
                key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
                dependencies=[submission_manually_graded_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            generated_feedback_assets[f"A{assignment_id}_S{student_id}"] = generated_feedback_asset

            # -----------------------------------------------------------------------------
            # dependencies: returned_feedback_asset -> generated_feedback_asset
            returned_feedback_asset = ReturnedFeedbackAsset(
                key=f"ReturnedFeedback_A{assignment_id}_S{student_id}",
                dependencies=[generated_feedback_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            returned_feedback_assets[f"A{assignment_id}_S{student_id}"] = returned_feedback_asset

            # -----------------------------------------------------------------------------
            # dependencies: uploaded_grade_asset -> submission_manually_graded_asset
            uploaded_grade_asset = UploadedGradeAsset(
                key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
                dependencies=[submission_manually_graded_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            uploaded_grade_assets[f"A{assignment_id}_S{student_id}"] = uploaded_grade_asset

            # -----------------------------------------------------------------------------
            # dependencies: returned_solution_asset -> [deadline_asset, submitted_fraction_asset]
            returned_solution_asset = ReturnedSolutionAsset(
                key=f"ReturnedSolution_A{assignment_id}_S{student_id}",
                dependencies=[deadline_asset, submitted_fraction_asset],
                resources=None,
                group=assignment_id,
                subgroup=student_id)

            returned_solution_assets[f"A{assignment_id}_S{student_id}"] = returned_solution_asset

            # -----------------------------------------------------------------------------

            # -----------------------------------------------------------------------------

    g.add_assets(list(grader_account_assets.values()))
    g.add_assets(list(deadline_assets.values()))
    g.add_assets(list(submission_raw_assets.values()))
    g.add_assets(list(submission_cleaned_assets.values()))
    g.add_assets(list(submission_auto_graded_assets.values()))
    g.add_assets(list(submission_manually_graded_assets.values()))
    g.add_assets(list(generated_feedback_assets.values()))
    g.add_assets(list(returned_feedback_assets.values()))
    g.add_assets(list(uploaded_grade_assets.values()))
    g.add_assets(list(returned_solution_assets.values()))

    g.summarize()
    print("refresh")
    input()

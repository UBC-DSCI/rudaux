import fwirl
import pendulum as plm
from typing import Dict

from fwirl import AssetStatus

from rudaux.fwirl_components.resources import LMSResource
from rudaux.model.student import Student
from rudaux.model.assignment import Assignment
from fwirl.resource import Resource
from fwirl.worker import GraphWorker

from rudaux.flows import load_settings
from rudaux.model import Settings
from rudaux.task.learning_management_system import get_assignments, get_students, get_course_section_info
from rudaux.tasks import get_learning_management_system, get_submission_system, get_grading_system


# ------------------------------------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------------------------------------
class AssignmentsListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, lms_resource: LMSResource,
                 min_polling_interval, course_section_name: str):
        self._built = False
        self._ts = None
        self.course_section_name = course_section_name
        self.lms_resource = lms_resource
        super().__init__(key=key, dependencies=dependencies,
                         resources=[self.lms_resource],
                         group=0, subgroup=0,
                         min_polling_interval=min_polling_interval)

    async def get(self) -> Dict[str, Assignment]:
        return self.lms_resource.get_assignments(course_section_name=self.course_section_name)

    def diff(self, val: Dict[str, Assignment]):
        # if self._cached_val != AssetStatus.Unavailable:
        #     cached_val_copy = self._cached_val.copy()
        #     for assignment_id, assignment in val.items():
        #         if assignment_id in self._cached_val:
        #             if self._cached_val[assignment_id] == assignment:
        #                 del cached_val_copy[assignment_id]
        #             else:
        #                 return False
        #         else:
        #             return False
        #     if len(cached_val_copy) != 0:
        #         return False
        #     return True
        # return False
        return val != self._cached_val


# ------------------------------------------------------------------------------------------------
class StudentsListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, lms_resource: LMSResource,
                 min_polling_interval, course_section_name: str):
        self._built = False
        self._ts = None
        self.course_section_name = course_section_name
        self.lms_resource = lms_resource
        super().__init__(key=key, dependencies=dependencies,
                         resources=[self.lms_resource],
                         group=0, subgroup=0,
                         min_polling_interval=min_polling_interval)

    async def get(self) -> Dict[str, Student]:
        return self.lms_resource.get_students(course_section_name=self.course_section_name)

    def diff(self, val: Dict[str, Student]):
        return val != self._cached_val


# ------------------------------------------------------------------------------------------------
class GradersListAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, resources=None, group=None, subgroup=None):
        self._built = False
        self._ts = None
        super().__init__(key, dependencies, resources, group, subgroup)

    async def get(self):
        pass

    def diff(self, val):
        # compare to self._cached_val
        pass


# ------------------------------------------------------------------------------------------------
class DeadlineAsset(fwirl.ExternalAsset):
    def __init__(self, key, dependencies, lms_resource,
                 student: Student, assignment: Assignment):
        self._built = False
        self._ts = None
        self.lms_resource = lms_resource
        self.student = student
        self.assignment = assignment
        group = assignment.lms_id  # assignment_id
        subgroup = student.lms_id  # student_id
        super().__init__(key=key, dependencies=dependencies,
                         resources=[self.lms_resource],
                         group=group, subgroup=subgroup,
                         min_polling_interval=1)

    async def get(self):
        self._cached_val = dict()
        for override_id, override in self.assignment.overrides.items():
            for student_id, student in override.students.items():
                if student_id == self.student.lms_id:
                    self._cached_val['due_at'] = override.due_at
                    break

    # collects the value of the resource

    def diff(self, val):
        # compare to self._cached_val
        pass


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

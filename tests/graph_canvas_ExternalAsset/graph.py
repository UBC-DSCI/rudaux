import os
import pendulum as plm
import yaml

import fwirl

from rudaux.flows import load_settings
from rudaux.model import Submission, Student, Grader, Assignment, CourseSectionInfo
from rudaux.interface.base.submission_system import SubmissionGradingStatus
from rudaux.fwirl_components.resources import LMSResource

import pdb

config_path='./rudaux_config.yml'

config = load_settings(config_path)

course_section_name = "section_dsci_100_test_01"

# Load LMS resource
lmsresource = LMSResource(key='lmsresource',settings=config,min_query_interval=10,course_name="course_dsci_100_test")

# Canvas course section info external asset
# Gets info about the Canvas course section (id, name, code, start at, end at, timezone)
class CanvasCourseInfoExternalAsset(fwirl.ExternalAsset):
    async def get(self):
        lmsresource = next(r for r in self.resources if r.key == 'lmsresource')
        course_section_info = lmsresource.get_course_section_info(course_section_name=course_section_name)
        return course_section_info

    # Diff start_at, end_at, and time_zone attributes
    async def diff(self, val):
        if self._cached_val is None:
            return True
        else:
            def _attrs(x):
                    return (x.start_at, x.end_at, x.time_zone)
            return _attrs(val) != _attrs(self._cached_val)

# Canvas student enrollment external asset
# Gets the class list of a Canvas course
class CanvasEnrollmentExternalAsset(fwirl.ExternalAsset):
    async def get(self):
        lmsresource = next(r for r in self.resources if r.key == 'lmsresource')
        student_enrollment = lmsresource.get_students(course_section_name=course_section_name)
        return student_enrollment

    # Diff students dict keys i.e. student lms ids, if keys are different replace cached value
    async def diff(self, val):
        if self._cached_val is None:
            return True
        else:
            return val.keys() != self._cached_val.keys()

# Canvas assignments external asset
# Gets list of Canvas assignments
class CanvasAssignmentsExternalAsset(fwirl.ExternalAsset):
    async def get(self):
        lmsresource = next(r for r in self.resources if r.key == 'lmsresource')
        assignments = lmsresource.get_assignments(course_section_name=course_section_name)
        return assignments

    # Diff assignment dict keys, if not different then compare each assignment entry
    async def diff(self, val):
        if self._cached_val is None:
            return True
        elif val.keys() != self._cached_val.keys():
            return True
        else:
            for a in val:
                def _attrs(x):
                    return (x.name, x.due_at, x.lock_at, x.unlock_at, x.overrides.keys(),
                            x.only_visible_to_overrides, x.published, x.skip)
                cached = self._cached_val[a.id]
                if _attrs(val) != _attrs(cached):
                    return True

canvas_course_info_asset = CanvasCourseInfoExternalAsset(
            key=f"CourseInfo_C{config['canvas_course_lms_ids']['section_dsci_100_test_01']}",
            dependencies=[],
            resources=[lmsresource],
            group=None,
            subgroup=None)

canvas_enrollment_asset = CanvasEnrollmentExternalAsset(
            key=f"Enrollment_C{config['canvas_course_lms_ids']['section_dsci_100_test_01']}",
            dependencies=[],
            resources=[lmsresource],
            group=None,
            subgroup=None)

canvas_assignments_asset = CanvasAssignmentsExternalAsset(
            key=f"Assignments_C{config['canvas_course_lms_ids']['section_dsci_100_test_01']}",
            dependencies=[],
            resources=[lmsresource],
            group=None,
            subgroup=None)
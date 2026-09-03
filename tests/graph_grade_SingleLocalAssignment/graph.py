import os
import pendulum as plm
import yaml

import fwirl

from rudaux.flows import load_settings
#from rudaux.tasks import get_grading_system
from rudaux.model import Submission, Student, Grader, Assignment, CourseSectionInfo
from rudaux.fwirl_components.resources import GradingSystemResource
from rudaux.interface.base.submission_system import SubmissionGradingStatus

import pdb

config_path='./rudaux_config.yml'

with open(config_path) as f:
    config = yaml.safe_load(f)

# Test values
course_name = 'course_dsci_100_test'
course_section_name = 'section_dsci_100_test_01'
grader_name = 'test_dir_courserepo'
assignment_id = '5678'
student_id = '1234'
assignment_name = 'tutorial_intro'

course_section_info = CourseSectionInfo(lms_id='5555', name='003', code='DSCI 100', start_at=plm.now(), end_at=plm.now(), time_zone='America/Vancouver')
assignment = Assignment(lms_id=assignment_id, name=assignment_name, due_at=plm.now(), lock_at=plm.now(), unlock_at=plm.now(), overrides={}, published=True, course_section_info=course_section_info, skip=False)
student = Student(lms_id=student_id, name='test student', sortable_name='test student', school_id='?', reg_date=plm.now(), status='?')

grader_root = config["nbgrader_user_root"] # points to CWD in testing
subm_folder = config["nbgrader_submissions_folder"] 
autograded_folder = config["nbgrader_autograded_folder"]
feedback_folder = config["nbgrader_feedback_folder"]
nbgrader_path = config["nbgrader_path"]

subm_file_path = os.path.join(grader_root,
                        grader_name,
                        nbgrader_path,
                        subm_folder,
                        config["nbgrader_student_folder_prefix"]+student_id,
                        assignment_name,
                        assignment_name+'.ipynb')



autograded_file_path = os.path.join(grader_root,
                        grader_name,
                        nbgrader_path,
                        autograded_folder,
                        config["nbgrader_student_folder_prefix"]+student_id,
                        assignment_name,
                        assignment_name+'.ipynb')

feedback_file_path = os.path.join(grader_root,
                        grader_name,
                        nbgrader_path,
                        feedback_folder,
                        config["nbgrader_student_folder_prefix"]+student_id,
                        assignment_name,
                        assignment_name+'.html')

grader = Grader(name=grader_name, info={'assignment_name':assignment.name, 'collected_assignment_path':subm_file_path,'autograded_assignment_path':autograded_file_path, 'generated_feedback_path':feedback_file_path,'folder':os.path.abspath(os.path.join(grader_root,grader_name,'R'))}, skip=False)
submission = Submission(lms_id='34567890', student=student, assignment=assignment, score=0, posted_at=None, late=False, missing=False, excused=False, course_section_info=course_section_info, grader=grader, status=SubmissionGradingStatus.ASSIGNED, skip=False)

# Initialize graph
graph = fwirl.AssetGraph("rudaux_graph")

# Generated assignment with gradebook.db file
class GeneratedAssignmentAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(GeneratedAssignmentAsset,self).__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        gradsys = next(r for r in self.resources if r.key == 'gradsysresource')
        gradsys.generate_assignment(grader)
        self._built = True
        self._ts = plm.now()
    
    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

# Submitted raw notebook in grader account directory submitted/student-*/*.ipynb
class SubmissionRawAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(SubmissionRawAsset,self).__init__(key, dependencies, resources, group, subgroup)

    
    # Download student submission from student server with SCP and place in grader folder
    # Then confirm if submission exists in grader's submitted directory
    async def build(self):
        # TODO: Code to download student submission from student server with SCP

        if os.path.exists(grader.info['collected_assignment_path']):
            self._built = True
            self._ts = plm.now()
        else:
            raise Exception(f"Raw submission notebook {grader.info['collected_assignment_path']} does not exist.")
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

# Submitted and cleaned notebook in grader account directory submitted/student-*/*.ipynb
class SubmissionCleanedAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(SubmissionCleanedAsset,self).__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        gradsys = next(r for r in self.resources if r.key == 'gradsysresource')
        gradsys.clean_submission(submission)
        self._built = True
        self._ts = plm.now()
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable

# Autograded submission + notebook in grader account directory autograded/student-*/*.ipynb
class SubmissionAutogradedAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(SubmissionAutogradedAsset,self).__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        gradsys = next(r for r in self.resources if r.key == 'gradsysresource')
        gradsys.autograde_submission(submission)

        if os.path.exists(grader.info['autograded_assignment_path']):
            self._built = True
            self._ts = plm.now()
        else:
            raise Exception(f"Autograded notebook {grader.info['autograded_assignment_path']} does not exist.")
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable
    
# Manually graded submission
class SubmissionManuallyGradedAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(SubmissionManuallyGradedAsset,self).__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        gradsys = next(r for r in self.resources if r.key == 'gradsysresource')
        gradsys.check_manual_grading(submission)

        if submission.status is SubmissionGradingStatus.DONE_GRADING:
            self._built = True
            self._ts = plm.now()
        else:
            raise Exception(f"Submission {submission.assignment.name} for {submission.student.name} LMS ID {submission.student.lms_id} needs manual grade.")
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable    
    
# Feedback notebook in grader account directory feedback/student-*/*.ipynb
class GeneratedFeedbackAsset(fwirl.Asset):
    def __init__(self, key, dependencies, resources = None, group = None, subgroup = None):
        self._built = False
        super(GeneratedFeedbackAsset,self).__init__(key, dependencies, resources, group, subgroup)

    async def build(self):
        gradsys = next(r for r in self.resources if r.key == 'gradsysresource')
        gradsys.generate_feedback(submission)

        if os.path.exists(grader.info['generated_feedback_path']):
            self._built = True
            self._ts = plm.now()
        else:
            raise Exception(f"Autograded notebook {grader.info['generated_feedback_path']} does not exist.")
        return 3

    async def timestamp(self):
        return self._ts if self._built else fwirl.AssetStatus.Unavailable
    
# Initialize assets for single student and assignment

test_assets = []

gradsysresource = GradingSystemResource(key='gradsysresource',settings=config,course_name=course_name)

generated_assignment_asset = GeneratedAssignmentAsset(
            key=f"GeneratedAssignment_A{assignment_id}_S{student_id}",
            dependencies=[],
            resources=[gradsysresource],
            group=assignment_id,
            subgroup=student_id)

test_assets.append(generated_assignment_asset)

submission_raw_asset = SubmissionRawAsset(
            key=f"SubmissionRaw_A{assignment_id}_S{student_id}",
            dependencies=[generated_assignment_asset],
            resources=None,
            group=assignment_id,
            subgroup=student_id)

test_assets.append(submission_raw_asset)

submission_cleaned_asset = SubmissionCleanedAsset(
            key=f"SubmissionCleaned_A{assignment_id}_S{student_id}",
            dependencies=[submission_raw_asset],
            resources=[gradsysresource],
            group=assignment_id,
            subgroup=student_id)

test_assets.append(submission_cleaned_asset)

submission_autograded_asset = SubmissionAutogradedAsset(
            key=f"SubmissionAutoGraded_A{assignment_id}_S{student_id}",
            dependencies=[submission_cleaned_asset],
            resources=[gradsysresource],
            group=assignment_id,
            subgroup=student_id)

test_assets.append(submission_autograded_asset)

submission_manually_graded_asset = SubmissionManuallyGradedAsset(
            key=f"SubmissionManuallyGraded_A{assignment_id}_S{student_id}",
            dependencies=[submission_autograded_asset],
            resources=[gradsysresource],
            group=assignment_id,
            subgroup=student_id)

test_assets.append(submission_manually_graded_asset)

generated_feedback_asset = GeneratedFeedbackAsset(
            key=f"GeneratedFeedback_A{assignment_id}_S{student_id}",
            dependencies=[submission_manually_graded_asset],
            resources=[gradsysresource],
            group=assignment_id,
            subgroup=student_id)

test_assets.append(generated_feedback_asset)

graph.add_assets(test_assets)

graph.run()
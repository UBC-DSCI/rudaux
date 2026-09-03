from loguru import logger

import yaml
import pendulum as plm
import os
import shutil

from rudaux.model import Submission, Student, Grader, Assignment, CourseSectionInfo
from rudaux.fwirl_components.resources import GradingSystemResource
from rudaux.interface.base.submission_system import SubmissionGradingStatus
from rudaux.fwirl_components.resources import GradingSystemResource
from rudaux.model import Grader
from rudaux.util.util import recursive_chown

config_path='./rudaux_config.yml'

with open(config_path) as f:
    config = yaml.safe_load(f)

gsr = GradingSystemResource(key='gradsysresource',settings=config, course_name="course_dsci_100_test")

# Testing vars
course_name="course_dsci_100_test"
assignment_name="tutorial_wrangling"
username="mockgrader"
skip=False

### Build grader object ###

grader1 = gsr.build_grader(course_name, assignment_name, username, skip)
logger.info("Grader built:")
logger.info(grader1)

### Initialize grader ###
# create_grading_volume
# _clone_git_repository(grader=grader)
# _create_submission_folder(grader=grader)
# generate_assignment(grader=grader)
# generate_solution(grader=grader)
# _initialize_account(grader=grader)
gsr.initialize_graders([grader1])
logger.info("Grader initialized")

### Assign submission to grader ###

# create a mock submission
course_section_name = 'section_dsci_100_test_01'
assignment_id = '5678'
student_id = '1234'

course_section_info = CourseSectionInfo(lms_id='5555', name='003', code='DSCI 100', start_at=plm.now(), end_at=plm.now(), time_zone='America/Vancouver')
assignment = Assignment(lms_id=assignment_id, name=assignment_name, due_at=plm.now(), lock_at=plm.now(), unlock_at=plm.now(), overrides={}, published=True, course_section_info=course_section_info, skip=False, only_visible_to_overrides=False)
student = Student(lms_id=student_id, name='test student', sortable_name='test student', school_id='?', reg_date=plm.now(), status='?')
submission = Submission(lms_id='34567890', student=student, assignment=assignment, score=0, posted_at=None, late=False, missing=False, excused=False, course_section_info=course_section_info, grader=None, status=SubmissionGradingStatus.NOT_ASSIGNED, skip=False)

logger.info("Mock submission before assigning submission:")
logger.info(submission)

gsr.assign_submission_to_grader([grader1],submission)

logger.info("Mock submission after assigning submission:")
logger.info(submission)
logger.info("Grader workload after being assigned submission:")
logger.info(grader1.info['workload'])

### Collect submission ###

# Wait until SSH implementation of submission system to uncomment
# gsr.collect_grader_submission(submission)

# Workaround until SSH submission system

# Remove submission from last test run
# if os.path.exists(grader1.info['collected_assignment_path']):
#     os.remove(grader1.info['collected_assignment_path'])

if not os.path.exists(grader1.info['collected_assignment_path']):
    dst_dir = os.path.dirname(grader1.info['collected_assignment_path'])
    os.makedirs(dst_dir, exist_ok=True)
    recursive_chown(dst_dir,
                    'jovyan',
                    'stty2u')

    shutil.copy('./student-1234/tutorial_wrangling/tutorial_wrangling.ipynb',
                grader1.info['collected_assignment_path'])

    recursive_chown(grader1.info['collected_assignment_folder'],
                    'jovyan',
                    'stty2u')

    submission.status = SubmissionGradingStatus.COLLECTED

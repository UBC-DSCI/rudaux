from loguru import logger

import yaml
import time
import pendulum as plm
from pendulum import DateTime, Timezone

from rudaux.fwirl_components.resources import LMSResource
from rudaux.model import Override, Student

import pdb

config_path='./rudaux_config.yml'

with open(config_path) as f:
    config = yaml.safe_load(f)

lmsresource = LMSResource(key='lmsresource',settings=config,min_query_interval=10,course_name="course_dsci_100_test")

logger.info(f"{lmsresource.course_name}, {lmsresource.lms.canvas_base_domain}, {lmsresource.lms.canvas_course_lms_ids}, {lmsresource.lms.assignments}")

# If need to call a API function more than once, change result_life_span to 0 in resources.py

course_section_info = lmsresource.get_course_section_info(course_section_name='section_dsci_100_test_01')

students = lmsresource.get_students(course_section_name='section_dsci_100_test_01')

instructors = lmsresource.get_instructors(course_section_name='section_dsci_100_test_01')

tas = lmsresource.get_tas(course_section_name='section_dsci_100_test_01')

assignments = lmsresource.get_assignments(course_section_name='section_dsci_100_test_01')

submissions_wks_intro = lmsresource.get_submissions(course_section_name='section_dsci_100_test_01', assignment=assignments['2421890'])

submissions_tut_intro = lmsresource.get_submissions(course_section_name='section_dsci_100_test_01', assignment=assignments['2421891'])

# Change submission score
submissions_wks_intro[0].score= 56.78

lmsresource.update_grade(course_section_name='section_dsci_100_test_01', submission=submissions_wks_intro[0])

override = assignments['2421890'].overrides['508888']

override.due_at = plm.tomorrow()

lmsresource.update_override(course_section_name='section_dsci_100_test_01', override=override)

existing_overrides = assignments['2421891'].overrides

lmsresource.delete_overrides(course_section_name='section_dsci_100_test_01', overrides=existing_overrides.values())

test_override = Override(lms_id='0', 
                         name='Late Reg 2773944', 
                         due_at=DateTime(2026, 4, 25, 0, 0, 0, tzinfo=Timezone('America/Los_Angeles')), 
                         lock_at=DateTime(2026, 5, 31, 6, 59, 59, tzinfo=Timezone('UTC')), 
                         unlock_at=DateTime(2026, 4, 1, 7, 0, 0, tzinfo=Timezone('UTC')),
                         students={'2773944':students['2773944']},
                         assignment_id='2421891',
                         course_section_info=course_section_info,
                         course_section_id=None)

lmsresource.create_overrides(course_section_name='section_dsci_100_test_01', overrides=[test_override])
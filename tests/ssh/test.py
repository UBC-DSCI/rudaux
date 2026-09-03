from loguru import logger

import yaml

from rudaux.fwirl_components.resources import SubmissionSystemResource
from rudaux.fwirl_components.resources import LMSResource
from rudaux.model.snapshot import Snapshot

import pdb

config_path='./rudaux_config.yml'

with open(config_path) as f:
    config = yaml.safe_load(f)

ssr = SubmissionSystemResource(key='subsysresource', settings=config, course_name="course_dsci_100_test", course_section_name='section_dsci_100_test_01')

lmsresource = LMSResource(key='lmsresource',settings=config,min_query_interval=10,course_name="course_dsci_100_test")

assignments = lmsresource.get_assignments(course_section_name='section_dsci_100_test_01')

students = lmsresource.get_students(course_section_name='section_dsci_100_test_01')

snapshots = ssr.list_snapshots('section_dsci_100_test_01', assignments, students)

test_snapshot = Snapshot(course_name='section_dsci_100_test_01',assignment=assignments['2380628'],student=None,override=None)

print(f'Test snapshot name: {test_snapshot.get_name()}')

ssr.take_snapshot('section_dsci_100_test_01',test_snapshot)

snapshots = ssr.list_snapshots('section_dsci_100_test_01', assignments, students)

print(f'{len(snapshots)} snapshots found.')

document = ssr.collect_snapshot('section_dsci_100_test_01', snapshots[1])

print(f'Document collected from snapshot: {document.info}')

ssr.distribute('section_dsci_100_test_01', snapshots[1].student, document, 'testfile.ipynb')
# import unittest
import time
from rudaux import Course, Assignment

start = time.time()
dsci100 = Course(course_dir='/Users/samhinshaw/projects/dsci100/DSCI_100_instructors')
# dsci100.get_students().sync_nbgrader().create_assignments_in_canvas()
dsci100.get_external_tool()
end = time.time()
print(f"{round(end - start, 2)} seconds elapsed")


class dsci100Assignment(Assignment):
  course = dsci100


lab_1 = dsci100Assignment(
  name="lab_1",
  duedate="2019-01-01",
  points=5,
  launch_url=
  r"https://c7l1-timberst.stat.ubc.ca/jupyter/hub/lti/launch?custom_next=/jupyter/hub/user-redirect/git-pull%3Frepo%3Dhttps%3A%2F%2Fgithub.com%2Fbinder-examples%2Frequirements%26subPath%3Dindex.ipynb",
)

lab_1.create_canvas_assignment(
  name=lab_1.name,
  submission_types=['external_tool'],
  external_tool_tag_attributes={
    "url": lab_1.launch_url,
    "new_tab": True,
    "content_id": dsci100.external_tool_id,
    "content_type": "context_external_tool"
  }
)

# dsci100.get_assignments_from_github().assign_all(overwrite=True)

# dsci100.create_assignments_in_canvas()

# dsci100.add_assignments_to_nbgrader()

# course.get_students()
# course.get_students().autograde('Alpha Romeo Tango Niner')

# course.get_assignments_from_canvas()
# dsci100.get_assignments_from_canvas() \
#        .schedule_grading()

# dsci100.get_students_from_canvas() \
#        .add_students_to_nbgrader()

# assn.assign(overwrite=True)

# course.get_assignments_from_canvas(
#   repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
#   dir='source',
#   pat_name='GHE_PAT',
#   exclude=['header.ipynb', 'scale_fruit_data.ipynb']
# ).create_assignments_in_canvas()
# course.get_assignments_from_canvas()

# dsci100.get_assignments_from_github()

# dsci100.get_assignments_from_github(
#   repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
#   dir='source',
#   exclude=['header.ipynb', 'scale_fruit_data.ipynb']
# ).assign()

# from assignment import Assignment

# homework1 = Assignment(name='homework_1', storage_dir='/tank/home')
# homework1.collect()
# homework1.grade()
# homework1.submit()

# homework1.assign(
#   pat_name='GHE_PAT',
#   ins_repo_url='https://github.ubc.ca/hinshaws/DSCI_100_instructors',
#   stu_repo_url='https://github.ubc.ca/hinshaws/DSCI_100_students',
#   overwrite=True
# )

# Assignment(name='homework_1').assign(
#   pat_name='GHE_PAT',
#   ins_repo_url='https://github.ubc.ca/hinshaws/DSCI_100_instructors',
#   stu_repo_url='https://github.ubc.ca/hinshaws/DSCI_100_students',
#   overwrite=True
# )

# Assignment(
#   name='lab_1',
#   github={
#     "ins_repo_url": 'https://github.ubc.ca/hinshaws/DSCI_100_instructors',
#     "stu_repo_url": 'https://github.ubc.ca/hinshaws/DSCI_100_students'
#   }
# ).assign(
#   pat_name='GHE_PAT', overwrite=True
# )

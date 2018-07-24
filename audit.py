# import unittest
from course import Course
from assignment import Assignment

dsci100 = Course(
  course_id=5394,
  canvas_url='https://ubc.test.instructure.com',
  stu_repo_url='https://github.ubc.ca/hinshaws/dsci_100_students',
  ins_repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
  hub_url='https://c7l1-timberst.stat.ubc.ca',
  hub_prefix='/jupyter',
  github_token_name='GHE_PAT'
)

dsci100.get_assignments_from_github().assign_all(
  stu_assignment_path='homeworks', overwrite=True
)

dsci100.create_assignments_in_canvas()

# dsci100.add_assignments_to_nbgrader()

# dsci100 = Course(
#   canvas_url='https://ubc.test.instructure.com',
#   hub_url='https://c7l1-timberst.stat.ubc.ca',
#   stu_repo_url='https://github.ubc.ca/hinshaws/dsci_100_students',
#   ins_repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
#   hub_prefix='/jupyter',
#   github_token_name='GHE_PAT'
# )

# course.get_students()
# course.get_students().autograde('Alpha Romeo Tango Niner')

# course.get_assignments_from_canvas()
# dsci100.get_assignments_from_canvas() \
#        .schedule_grading()

# course.get_assignments_from_github(
#   repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
#   dir='source',
#   pat_name='GHE_PAT',
#   exclude=['header.ipynb', 'scale_fruit_data.ipynb']
# ).create_assignments_in_canvas(overwrite=True)

# dsci100.get_assignments_from_github(
#   repo_url='https://github.ubc.ca/hinshaws/dsci_100_instructors',
#   dir='source',
#   exclude=['header.ipynb', 'scale_fruit_data.ipynb']
# ).create_assignments_in_canvas()

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

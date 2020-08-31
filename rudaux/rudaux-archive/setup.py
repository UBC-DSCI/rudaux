from setuptools import setup, find_packages

requirements = []
with open('requirements.txt', 'r') as in_:
  requirements = in_.readlines()

setup(
  name='rudaux',
  version='0.3',
  description='Canvas Course Management with JupyterHub & nbgrader.',
  long_description=
  'This packages provides automation for managing a course that uses JupyterHub & nbgrader along with the Canvas Learning Management System.',
  url='http://github.com/samhinshaw/rudaux',
  author='Sam Hinshaw',
  author_email='samuel.hinshaw@gmail.com',
  license='BSD',
  packages=find_packages(),
  zip_safe=False,
  install_requires=requirements,
  # entry_points={
  #   'console_scripts':
  #     [
  #       'initialize-course=rudaux.commands:initialize_course',
  #       # 'initialize-course-overwrite=rudaux.command_line:initialize_course_overwrite'
  #       'schedule-grading=rudaux.commands:schedule_grading',
  #     ],
  # },
  scripts=['bin/rudaux']
)

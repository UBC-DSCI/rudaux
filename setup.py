from setuptools import setup, find_packages
from rudaux import __version__

requirements = []
with open('requirements.txt', 'r') as in_:
  requirements = in_.readlines()

setup(
  name='rudaux',
  version=__version__,
  description='Course management software for orchestrating auto/manual grading workflows.',
  author='Trevor Campbell',
  author_email='trevor.d.campbell@gmail.com',
  license='BSD',
  packages=find_packages(),
  zip_safe=False,
  install_requires=requirements,
  scripts=['bin/rudaux']
)

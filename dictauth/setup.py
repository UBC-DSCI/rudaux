from setuptools import setup, find_packages
from dictauth import __version__

requirements = []
with open('requirements.txt', 'r') as in_:
  requirements = in_.readlines()

setup(
  name='dictauth',
  version=__version__,
  description='Dictionary Authentication tools for JupyterHub.',
  author='Trevor Campbell',
  author_email='trevor.d.campbell@gmail.com',
  license='BSD',
  packages=find_packages(),
  zip_safe=False,
  install_requires=requirements,
  scripts=['bin/dictauth']
)

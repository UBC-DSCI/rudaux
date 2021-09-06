from setuptools import setup, find_packages

requirements = []
with open('requirements.txt', 'r') as in_:
  requirements = in_.readlines()

setup(
  name='dictauth',
  version='0.2.0',
  description='Dictionary Authentication tools for JupyterHub.',
  author='Trevor Campbell',
  author_email='trevor.d.campbell@gmail.com',
  license='BSD',
  packages=find_packages(),
  zip_safe=False,
  install_requires=requirements,
  scripts=['bin/dictauth']
)

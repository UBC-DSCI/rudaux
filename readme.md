## rudaux 

![](https://github.com/UBC-DSCI/rudaux/workflows/build/badge.svg) [![codecov](https://codecov.io/gh/UBC-DSCI/rudaux/branch/master/graph/badge.svg)](https://codecov.io/gh/UBC-DSCI/rudaux) ![Release](https://github.com/UBC-DSCI/rudaux/workflows/Release/badge.svg)

[![Documentation Status](https://readthedocs.org/projects/rudaux/badge/?version=latest)](https://rudaux.readthedocs.io/en/latest/?badge=latest)

This packages provides automation for managing a course that uses JupyterHub & nbgrader along wwith a learning management system (e.g., Canvas, EdX).

Rudaux helps you programmatically administer a course by integrating:

- [Canvas](https://www.canvaslms.com/) - a learning management system
- [JupyterHub](https://github.com/jupyterhub/jupyterhub) - a multi-user Jupyter notebook Server
- [nbgrader](https://github.com/jupyter/nbgrader) - a Jupyter notebook auto-grader
- [nbgitpuller](https://github.com/data-8/nbgitpuller) - a JupyterHub extension to pull Jupyter notebooks from git repositories

Rudaux was designed to simplify course management generally, but there are a few operations in particular that would be nearly impossible without rudaux.

- Syncing students and assignments between Canvas and nbgrader.
- Creating assignments in Canvas with JupyterHub/nbgitpuller links.
- Scheduled automated grading of Jupyter notebooks with nbgrader.

Rudaux is named after the French artist and astronomer Lucien Rudaux, a pioneer in space artistry and one of the first artists to paint Jupiter.

<figure>
  <img src="img/rudaux_jupiter.jpg" alt='"Jupiter Seen from Io" by Lucien Rudaux' style="border-radius: 20px;">
  <figcaption>"Jupiter Seen from Io" by Lucien Rudaux</figcaption>
</figure>


### Installation:

```
pip install -i https://test.pypi.org/simple/ rudaux
```

### Features
- TODO

### Dependencies

- TODO

### Usage

- TODO

### Documentation
The official documentation is hosted on Read the Docs: <https://rudaux.readthedocs.io/en/latest/>

### Credits
This package was created with Cookiecutter and the UBC-MDS/cookiecutter-ubc-mds project template, modified from the [pyOpenSci/cookiecutter-pyopensci](https://github.com/pyOpenSci/cookiecutter-pyopensci) project template and the [audreyr/cookiecutter-pypackage](https://github.com/audreyr/cookiecutter-pypackage).

### Modifications to remember when writing docs
- Nginx remove `client_max_body_size` constraint for saving notebooks
- timeout extension in LTAuth for slow logins
- websockets fix for login issues
- restart VM for DockerAPIError create containers
- NFS setup
```
yum install nfs-utils
systemctl start nfs-server
zfs set sharenfs='rw=@IP.ADDRESS.FOR.INSTRUCTOR.HUB/32,crossmnt,no_root_squash' tank/home
firewall-cmd --permanent --add-rich-rule='rule family=ipv4 source address=IP.ADDRESS.FOR.INSTRUCTOR.HUB/32 port port=2049 protocol=tcp accept'
```

# Rudaux

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
  <img src="rudaux_jupiter.jpg" alt='"Jupiter Seen from Io" by Lucien Rudaux' style="border-radius: 20px;">
  <figcaption>"Jupiter Seen from Io" by Lucien Rudaux</figcaption>
</figure>

## Documentation

For a full usage guide, please see the [rudaux documentation](https://samhinshaw.github.io/rudaux-docs), or my blog posts on [designing rudaux](https://samhinshaw.com/blog/designing-rudaux) and [using rudaux](https://samhinshaw.com/blog/using-rudaux).

### Installation

```
pip install rudaux
```

### Setup

Before setting up rudaux, it is important to have the proper infrastructure in place. Please see the [DSCI 100 infrastructure repository](https://github.ubc.ca/UBC-DSCI/dsc100-infra) for our reproducible infrastructure provisioning workflow.

_Note_: rudaux currently requires a fork of nbgrader to work properly ([more information](https://github.com/samhinshaw/rudaux/issues/7)):

```sh
pip install git+git://github.com/samhinshaw/nbgrader.git
```

Once your servers are set up and your dependencies installed, rudaux needs a configuration file to operate. Please read the [configuration](config) documentation for more information and a sample config file.

1. Log in to the server you will be executing rudaux commands on.
2. Clone your instructors repository containing your config file and master (source) assignments.
3. Initialize rudaux.

### Usage

#### Command-Line Interface

See [command-line interface](https://samhinshaw.github.io/rudaux-docs/cli/).

```sh
rudaux {init, grade, submit}
```

#### Python API

See [API](https://samhinshaw.github.io/rudaux-docs/api/).

```py
from rudaux import Course, Assignment
```

# Rudaux

Rudaux is a course management module to interface the Canvas Learning Management System (LMS) with JupyterHub. Rudaux helps you programmatially administer a course being taught in JupyterHub

Rudaux assists in:

- true autograding - scheduling `cron` events to kick off [`nbgrader`](https://github.com/jupyter/nbgrader) autograding
- creating assignments in Canvas with links to your JupyterHub notebooks using [`nbgitpuller`](https://github.com/data-8/nbgitpuller)

Rudaux is named after the French artist and astronomer Lucien Rudaux who was a pioneer in space artistry and one of the first artists to paint Jupiter.

![Jupiter Seen from Io by Lucien Rudaux](rudaux_jupiter.jpg)

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

#### Module Import

See [modules](https://samhinshaw.github.io/rudaux-docs/modules/).

```py
from rudaux import Course, Assignment
```

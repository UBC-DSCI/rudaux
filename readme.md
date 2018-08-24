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

## Testing with Rudaux

You can test out rudaux on your own computer without the need to set up any servers! To get started, you will need a few things.

1. Access to a [Canvas test environment](https://community.canvaslms.com/docs/DOC-13011-4152719755).
2. A test instructors' repository with your source assignments and your [config file](https://ubc-dsci.github.io/rudaux-docs/config/).
3. A test students' repository.
4. Docker, `rudaux` and `nbgrader` installed.
5. Your Docker grading image installed from DockerHub.
6. A [token](https://canvas.instructure.com/doc/api/file.oauth.html#manual-token-generation) from your Canvas test environment.

Make sure you change the options in your config file to match your test environment. Some important options include:

- `c.Canvas.canvas_url` = url of your Canvas test environment
- `c.JupyterHub.storage_path` = location on your computer where student submissions would be collected from
- `c.GitHub.ins_repo_url` = test instructors repo
- `c.GitHub.stu_repo_url` = test students repo
- `c.Canvas.token_name` = name of the environment variable storing your Canvas token

Then, go for it! One important thing to note is that if you run `.schedule_grading()`, which is part of `rudaux init`, rudaux will schedule jobs to your crontab. You should be aware of this, and may want to delete them manually upon conclusion of your testing.

## Contributing

To develop rudaux, clone this repository. Then, you can install it locally and begin testing it!

### Deployment to PyPI

- Update the version number in setup.py.
- Then, run the following commands.

  ```sh
  python setup.py sdist upload
  python setup.py bdist_wheel upload
  ```

- When prompted for password, enter your PyPI password.

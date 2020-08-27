## Set up AWS cloud architecture

As stated earlier, running a course with [`rudaux`](https://github.com/UBC-DSCI/rudaux) requires 3 pieces of AWS cloud architecture:

1. One AWS EC2 instance will be used to host and serve the student JupyterHub (where students will complete their homework).

2. One AWS EC2 instance will be used to host and serve the grading JupyterHub (where the teaching team will perform grading and where the autograding will be done).

3. One Amazon elastic filesystem (EFS) mounted on both the student and grading JupyterHubs to allow for simple transfer of files between the two JupyterHubs for grading.

The following documentation will walk you through setting up each of these using the AWS web user interface.
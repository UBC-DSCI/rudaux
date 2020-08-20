## Inventory list

To run a course using [`rudaux`](https://github.com/UBC-DSCI/rudaux) you will need the following:

1. A Canvas course shell 
2. Two Amazon Web Services (AWS) EC2 instances
3. A laptop or desktop computer
4. Two domain names that are compatible with Let's Encrypt 

### Canvas course shell

The Canvas course shell will be used as the course learning management system that students access their assignments and view their assignment and course grades. At UBC, we use the Canvas course shells distributed by the University. If you do not have Canvas course shells provided by your University you can create a Canvas course shell using a free instance of Canvas accessible here: [https://canvas.instructure.com/](https://canvas.instructure.com/).

### Two Amazon Web Services (AWS) EC2 instances

The two Amazon Web Services (AWS) EC2 instances will be used to host and serve two JupyterHubs. One will be the JupyterHub that the students use to complete their homework. This student JupyterHub will use Canvas as the authentication. The second will be the JupyterHub that the course teaching team uses for auto- and manual grading. This grading JupyterHub will use Shibboleth for authentication. At UBC we use the teaching team's campus-wide login (CWL) as the username and password for this. The two JupyterHubs are "connected" by an Amazon Elastic File System (EFS) so that the grading JupyterHub can access the students work for grading purposes (i.e., students do not have to do anything to submit their assignments, other than saving their files on the student JupyterHub).

### A laptop or desktop computer

[`rudaux`](https://github.com/UBC-DSCI/rudaux) uses a dev ops tool named Ansible to automate much of the installation and setup of the two JupyterHubs. Ansible is run on your local laptop or desktop computer and uses the instructions in the `ansible` directory in the `rudaux` GitHub repository to send installation and configuration commands to the AWS EC2 instances to install and setup the two JupyterHubs. 

### Two domain names that are compatible with [Let's Encrypt](https://letsencrypt.org/)

To keep the JupyterHubs secure we use the HTTPS protocol. This is a protocol which requires browser-trusted certificates. We use the service [Let's Encrypt](https://letsencrypt.org/) to automate the process of obtaining a browser-trusted certificate. For this to work, you will need two domain names that are compatible with [Let's Encrypt](https://letsencrypt.org/).
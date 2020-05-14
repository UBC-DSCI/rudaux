# Deploying a Littlest Jupyterhub

This document details process changes that diverge from the instructions given in the [Littlest Jupyterhub](http://tljh.jupyter.org/en/latest/) setup instructions given by Jupyter.

## Passwords/Accounts

* The documentation is unclear on this, but you should enter the password you wish to use during your FIRST login; the docs make it appear as though you will be prompted to enter your password after you login, but this is not the case

## Security Groups

**ERROR:**
The orginal instructions require the creation of _new_ security groups. Not all users on AWS may have the correct roles/permissions to do so.

**SOLUTION:**
Simply select an existing security group in the _Configure Security Group_ stage of AWS instance deployment. Select the security group with the description: **default VPC security group**. 

## Virtual Machine/Server Troubleshooting
* **Can't connect to the AWS instance on a web browser**: try following [these instructions](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AccessingInstancesLinux.html)
* **Littlest Jupyterhub not installing**: the instructions on [installing TLJH on AWS](http://tljh.jupyter.org/en/latest/install/amazon.html) are outdated, you will need an instance with **more than 1GB memory** to successfully perform an installation
  * I found that 2GB memory was sufficient for installation; in AWS-speak, this is a t2.small instance.

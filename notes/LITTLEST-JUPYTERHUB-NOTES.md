# Deploying a Littlest Jupyterhub

This document details process changes that diverge from the instructions given in the [Littlest Jupyterhub](http://tljh.jupyter.org/en/latest/) setup instructions given by Jupyter.

## Security Groups

**ERROR:**
The orginal instructions require the creation of _new_ security groups. Not all users on AWS may have the correct roles/permissions to do so.

**SOLUTION:**
Simply select an existing security group in the _Configure Security Group_ sstage of AWS instance deployment. Select the security group with the description: **default VPC security group**. 

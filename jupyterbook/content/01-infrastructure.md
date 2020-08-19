# Course Infrastructure

## Inventory list
- Canvas course shell
- Two JupyterHub servers (each running on an AWS EC2 instance)
- Rudaux to build the JupyterHubs and connect the above

## Set up cloud servers to host the JupyterHubs

1. Log into the [AWS Management console](https://aws.amazon.com/console/) and search for EC2 in the AWS services search bar:

    ```{figure} img/ec2-1.png
    :alt: ec2-1
    :width: 500px
    :align: center
    ```

1. Scroll down and click on the orange "Launch Instance" button:

    ```{figure} img/ec2-1.png
    :alt: ec2-1
    :width: 500px
    :align: center
    ```

1. Search for the Centos 7.8 Community Amazon machine image (AMI) that has the id `ami-0252eebc56636a56b`:

    ```{figure} img/ec2-2.png
    :alt: ec2-2
    :width: 500px
    :align: center
    ```
    and select it:

    ```{figure} img/ec2-3.png
    :alt: ec2-3
    :width: 500px
    :align: center
    ```
    
1. Select an instance type (we use a m5.4xlarge for ~ 200 students) and click "Next: Configure Instance Details":
    
    ```{figure} img/ec2-4.png
    :alt: ec2-4
    :width: 500px
    :align: center
    ```

1. Leave these settings as is, and click on "Next: Add Storage":

    ```{figure} img/ec2-5.png
    :alt: ec2-5
    :width: 500px
    :align: center
    ```

1. Click the "Add New Volume" button twice to add two additional EBS volumes (one for the students' persistent filesystems, and one for Docker). Edit the sizes to be 30, 1024 and 128 for the root, students' persistent filesystems, and Docker volumes, respectively. Click the "Next: Add Tags" button:

    ```{figure} img/ec2-6.png
    :alt: ec2-6
    :width: 500px
    :align: center
    ```

1. Add a key and value pair to easily identify the machine later on your EC2 console (we used the key "Course" and value "workflows" here, but you can choose whatever is meaningful to you). Click the "Next: Configure Security Group" button:

    ```{figure} img/ec2-7.png
    :alt: ec2-7
    :width: 500px
    :align: center
    ```

1. 

    ```{figure} img/ec2-8.png
    :alt: ec2-8
    :width: 500px
    :align: center
    ```
1. Click the "Add Rule" button three times to add three additional security groups. Choose the one each of the following types: HTTP, HTTPS and All ICMP - IPv4. For the All ICMP - IPv4 security group, edit the value for the Source to be Custom and 0.0.0.0/0. Click the blue "Review and Launch" button:
 
    ```{figure} img/ec2-9.png
    :alt: ec2-9
    :width: 500px
    :align: center
    ```

1. Review your settings, and if satisfied, click the blue "Launch" button:

    ```{figure} img/ec2-10.png
    :alt: ec2-10
    :width: 500px
    :align: center
    ```
     
1. Choose "Create a new key pair" and create a "Key pair name" (here we used jupyterhub). Click "Download Key Pair" and then the blue "Launch Instance" button:
     
     
    ```{figure} img/ec2-11.png
    :alt: ec2-11
    :width: 500px
    :align: center
    ```
1. If successful, you should see this screen:

    ```{figure} img/ec2-12.png
    :alt: ec2-12
    :width: 500px
    :align: center
    ```
    
1. ADD INSTRUCTIONS ON HOW TO GET SSH INFO AND CONNECT
     

1. Add the Ansible machine's (e.g., your laptop's) public key to `~/.ssh/authorized_keys` on the EC2 instances.

## Setting up Ansible on your local machine

1. Install `conda`, either by installing [Miniconda](https://docs.conda.io/en/latest/miniconda.html#) (recommended) or [Anaconda](https://docs.anaconda.com/anaconda/install/).

1. Install Ansible on your local computer by typing in the following into a terminal: 

    ```
    conda install -c conda-forge ansible
    ```
## Build the JupyterHubs using Ansible

1. Copy the EC2 public IP addresses of the EC2 instances into ansible/inventory replacing <STUDENT_HUB_IP> and <GRADING_HUB_IP> respectively.

4. To test this is all setup correctly you can try pinging one of the hubs via:

ansible jhub-mastodon -m ping

5. Set the devices for the zfs snapshots and the docker images in group_vars/all/local_vars.yml. For example:
zfs_vdev_config: /dev/nvme1n1
openstack_ephemeral_docker_disk: /dev/nvme2n1

6. To run the setup step of the student hub, run the following command:

make ansible/setup ENV=prod
To run the init step of the student hub, run the following command:

make ansible/playbook PLAYBOOK=init ENV=prod
​

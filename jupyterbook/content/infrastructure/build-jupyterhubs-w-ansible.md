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

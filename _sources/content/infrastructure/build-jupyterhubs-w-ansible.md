## Setting up Ansible on your local machine

1. Install `conda`, either by installing [Miniconda](https://docs.conda.io/en/latest/miniconda.html#) (recommended) or [Anaconda](https://docs.anaconda.com/anaconda/install/).

1. Install Ansible on your local computer by typing in the following into a terminal: 

    ```
    conda install -c conda-forge ansible
    ```

## Add the variables specific to your course

1. Clone or download the [`rudaux`](https://github.com/UBC-DSCI/rudaux) repository.

2. Open `ansible/inventory` in a text editor and replace the `<STUDENT_HUB_DOMAIN>` with your [Let's Encrypt](https://letsencrypt.org/) compatible domain name for the student Jupyterhub. Also replace `<STUDENT_HUB_IP_ADDRESS>` with the IP address for your EC2 instance that will become the student JupyterHub (Reminder this is the value for the IPv4 Public IP address found under the "Description" tab for your EC2 instance on the AWS EC2 Dashboard).

3. Add any public IP addresses of folks you need to access the JupyterHubs via ssh (for IT purposes) in `ansible/group_vars/all/ssh-public-keys.yml`.

## Build the JupyterHubs using Ansible

1. To initialize the EC2 instance that will become the student JupyterHub (e.g., update all `yum` packages and reboot the machine) navigate to the `ansible` directory and run:

    ```
    make playbook PLAYBOOK=init ENV=prod
    ```

2. To install and configure the student JupyterHub run the following from the `ansible` directory:

    ```
    make playbook PLAYBOOK=hub ENV=prod
    ```
    

6. To run the setup step of the student hub, run the following command:

make ansible/setup ENV=prod
To run the init step of the student hub, run the following command:

#make ansible/playbook PLAYBOOK=init ENV=prod

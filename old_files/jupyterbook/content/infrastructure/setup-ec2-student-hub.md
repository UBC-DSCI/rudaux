## Set up EC2 instance for student JupyterHub

Follow the instructions below to setup an AWS EC2 instance which will be used to host and serve the student JupyterHub (where students will complete their homework).

1. Log into the [AWS Management console](https://aws.amazon.com/console/) and search for EC2 in the AWS services search bar:

    <br>

    ```{figure} img/ec2-1.png
    ---
    alt: ec2-1
    width: 500px
    align: center
    ---
    ```

    <br>

1. Scroll down and click on the orange "Launch Instance" button:

    <br>

    ```{figure} img/ec2-2.png
    :alt: ec2-2
    :width: 500px
    :align: center
    ```

    <br>
    
1. Search for the Centos 7.8 Community Amazon machine image (AMI) that has the id `ami-0252eebc56636a56b`:

    <br>

    ```{figure} img/ec2-3.png
    :alt: ec2-3
    :width: 500px
    :align: center
    ```
    
    <br>

    and select it:

    <br>  

    ```{figure} img/ec2-4.png
    :alt: ec2-4
    :width: 500px
    :align: center
    ```
    <br>    
    
1. Select an instance type (we use a m5.4xlarge for ~ 200 students) and click "Next: Configure Instance Details":
    
    <br>
    
    ```{figure} img/ec2-5.png
    :alt: ec2-5
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Leave these settings as is, and click on "Next: Add Storage":

    <br>  
    
    ```{figure} img/ec2-6.png
    :alt: ec2-6
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Click the "Add New Volume" button twice to add two additional EBS volumes (one for the students' persistent filesystems, and one for Docker). Edit the sizes to be 30, 1024 and 128 for the root, students' persistent filesystems, and Docker volumes, respectively. Click the "Next: Add Tags" button:

    <br>  
    
    ```{figure} img/ec2-7.png
    :alt: ec2-7
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Add a key and value pair to easily identify the machine later on your EC2 console (we used the key "Course" and value "workflows" here, but you can choose whatever is meaningful to you). Click the "Next: Configure Security Group" button:

    <br>  
    
    ```{figure} img/ec2-8.png
    :alt: ec2-8
    :width: 500px
    :align: center
    ```
    
    <br>  
    
1. Click the "Add Rule" button three times to add three additional security groups. Choose the one each of the following types: HTTP, HTTPS and All ICMP - IPv4. For the All ICMP - IPv4 security group, edit the value for the Source to be Custom and 0.0.0.0/0. Click the blue "Review and Launch" button:
 
    <br>  
    
    ```{figure} img/ec2-9.png
    :alt: ec2-9
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Review your settings, and if satisfied, click the blue "Launch" button:

    <br>  
    
    ```{figure} img/ec2-10.png
    :alt: ec2-10
    :width: 500px
    :align: center
    ```
    
    <br>  
     
1. Choose "Create a new key pair" and create a "Key pair name" (here we used jupyterhub). Click "Download Key Pair" and then the blue "Launch Instance" button:
     
    <br>  
     
    ```{figure} img/ec2-11.png
    :alt: ec2-11
    :width: 500px
    :align: center
    ```
    
    <br>  
    
    Save the key pair somewhere intentional on your laptop (e.g., `~/.ssh/`) and then type the following to update the permissions of the key:
    
    ```
    chmod 400 ~/.ssh/jupyterhub.pem
    ```
    
1. If successful, you should see this screen:

    <br>  

    ```{figure} img/ec2-12.png
    :alt: ec2-12
    :width: 500px
    :align: center
    ```
    
    <br>  
    
1. Go back to the EC2 Dashboard (reminder: you can get there via searching for EC2 in the AWS services search bar) and click on the "Running instances" link:

    <br>  

    ```{figure} img/ec2-13.png
    :alt: ec2-13
    :width: 500px
    :align: center
    ```

    <br>  

1. Select the instance you just launched and under the "Description" tab note (and record somewhere for future reference) the Public DNS (IPv4) value (which will be used to ssh into the instance) and the IPv4 Public IP address (which will be used by ansible and for mapping your custom domain name to the server):

    <br>  

    ```{figure} img/ec2-14.png
    :alt: ec2-14
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Add the Ansible machine's (e.g., your laptop's) public key to `~/.ssh/authorized_keys` on the EC2 instances. To do this you need to ssh into the EC2 instance using the private key you downloaded from Amazon earlier (`jupyterhub.pem` in this example):

    ```
    ssh -i ~/.ssh/jupyterhub.pem centos@ec2-3-96-44-97.ca-central-1.compute.amazonaws.com
    ```
    
    And then use The UNIX vi editor to add your public key the `~/.ssh/authorized_keys` file. To do this type the following to open vi:
    
    ```
    sudo vi ~/.ssh/authorized_keys
    ```
    
    Then press `i` to enter insert mode and paste your key using your OS's paste keyboard shortcut. Then press `ESC` + `w` + `q` to write the file and exit. Now you are are ready to move onto using Ansible to build the student JupyerHub.
    

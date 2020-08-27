## Set up Amazon Elastic Filesystem (EFS)

Follow the instructions below to setup an Amazon elastic filesystem (EFS) mounted on both the student and grading JupyterHubs to allow for simple transfer of files between the two JupyterHubs for grading.

1. Log into the [AWS Management console](https://aws.amazon.com/console/) and search for EFS in the AWS services search bar:

    <br>

    ```{figure} img/efs-1.png
    ---
    alt: efs-1
    width: 500px
    align: center
    ---
    ```

    <br>

1. Scroll down and click on the orange "Create file system" button:

    <br>

    ```{figure} img/efs-2.png
    :alt: efs-2
    :width: 500px
    :align: center
    ```

    <br>
    
1. Add a name for your file system (we called ours homework-to-grade) and click the white "Customize" button:

    <br>

    ```{figure} img/efs-3.png
    :alt: efs-3
    :width: 500px
    :align: center
    ```

    <br>    
    
1. Deselect "Enable automatic backups" (found under the "Automatic backups" header) and scroll down to the bottom of the screen and click the orange "Next" button:
    
    <br>
    
    ```{figure} img/efs-4.png
    :alt: efs-4
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Leave these settings as is, and click the orange "Next" button:

    <br>  
    
    ```{figure} img/efs-5.png
    :alt: efs-5
    :width: 500px
    :align: center
    ```
    
    <br>  

1. Leave these settings as is, and click the orange "Next" button:

    <br>  
    
    ```{figure} img/efs-6.png
    :alt: efs-6
    :width: 500px
    :align: center
    ```
    
    <br> 
    
1. Review your settings as is, and click the orange "Create" button:

    <br>  
    
    ```{figure} img/efs-7.png
    :alt: efs-7
    :width: 500px
    :align: center
    ```
    
    <br> 

1. You will then be sent to the EFS dashboard and you should be able to view the file system you just created. Record somewhere for future reference the File system ID for the file system you just created (for example, ours is `fs-35c65bd8`):

    <br>  
    
    ```{figure} img/efs-8.png
    :alt: efs-8
    :width: 500px
    :align: center
    ```

Now that you have setup the necessary AWS infrastructure, you can move onto using ansible to setup and install the JupyterHubs!
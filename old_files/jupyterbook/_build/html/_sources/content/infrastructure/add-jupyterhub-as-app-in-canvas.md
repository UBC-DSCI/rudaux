## Add JupyterHub as an App on Canvas

The final infrastructure step for this course is to add JupyterHub as an App to your Canvas course shell. Follow the steps below to do this.

> Note: If your University typically provides instructors their course shells (as is typically done at UBC) then the University IT/LT team may have to perform the steps outlined below:

1. In the Setting page, click on "View App Configuration"

    <br>

    ```{figure} img/canvas-1.png
    ---
    alt: canvas-1
    width: 500px
    align: center
    ---
    ```

    <br>
    
1. Next, click the blue "+App" button:

    <br>

    ```{figure} img/canvas-2.png
    ---
    alt: canvas-2
    width: 500px
    align: center
    ---
    ```

    <br>
    
1. On the Add App page, enter/select the values listed below, and then click the blue "Submit" button: 

    - Name (What you would like to call the app, here we call it JupyterHub)
    - Consumer Key (the output from `openssl rand -hex 32` that was set as `jupyterhub_lti_client_key` in `ansible/group_vars/hubs/secrets.yml`)
    - Shared Secret (the output from `openssl rand -hex 32` that was set as `jupyterhub_lti_client_secret` in `ansible/group_vars/hubs/secrets.yml`)
    - Launch URL (the Let's Encrypt compatible domain for the student JupyterHub concatenated with `/jupyter/hub/lti/launch`)
    - Privacy (set as Public)

    <br>

    ```{figure} img/canvas-3.png
    ---
    alt: canvas-3
    width: 500px
    align: center
    ---
    ```

    <br>
    
1. Now JupyterHub should be available as an App to your Canvas course shell. You can test this by trying to create an assignment and under Submission Type, select "External Tool" and click Find:

    <br>

    ```{figure} img/canvas-4.png
    ---
    alt: canvas-4
    width: 500px
    align: center
    ---
    ```

    <br>

1. You should be able to see the name of the App you just created:
    
    <br>

    ```{figure} img/canvas-5.png
    ---
    alt: canvas-5
    width: 500px
    align: center
    ---
    ```

    <br>

#!/usr/bin/env python
# coding: utf-8

# ## Setup `ruduax`
# 
# The Python package `rudaux` manages the assignment collection, auto- and manual grading, as well as posting grades, solutions and feedback. `rudaux` needs to be installed and configured on both the student and grading servers.
# 
# ### Setup `ruduax` on the student server
# 
# 1. In the home folder of your student server, clone the [`rudaux`](https://github.com/UBC-DSCI/rudaux) repo
# 
# 2. Open the `rudaux` package folder `rudaux/rudaux`, and do `sudo pip3 install . --upgrade`
# 
# 3. Fill out the template rudaux config in `rudaux/tests/rudaux_template_config.py` and put that in your home folder and rename it `rudaux/tests/rudaux_config.py`
# 
# 4. In the home folder run `sudo rudaux list`  -- this should successfully show you the list of students, tas, instructors, and Jupyterhub assignments
# 
# 5. Copy the cron job script `rudaux/rudaux/cron/rudaux_snapshot` into `/etc/cron.d/rudaux_snapshot`
# open it and make sure to replace the `/path/to/your/etc/` is your home folder, e.g. `/home/stty2u/`.
# 
# 

# ### Setup `ruduax` on the grading server
# 
# 1. In the home folder of your grading server, clone the [`rudaux`](https://github.com/UBC-DSCI/rudaux) repo
# 
# 2. Open the `rudaux` package folder `rudaux/rudaux`, and do `sudo pip3 install . --upgrade`
# 
# 3. Fill out the template rudaux config in `rudaux/tests/rudaux_template_config.py` and put that in your home folder and rename it `rudaux/tests/rudaux_config.py`
# 
# 4. Go to `rudaux/dictauth` and type `sudo pip3 install . --upgrade`
# 
# 5. Open up your `/srv/jupyterhub_config.py` file remove any LTAuthenticator lines and replace with 
#     ```
#     c.JupyterHub.authenticator_class = 'dictauth.DictionaryAuthenticator'
#     c.DictionaryAuthenticator.encrypted_passwords = {}
#     ```
#     
# 6. In the home folder, type `sudo dictauth list_users` -- should output an empty list
# 
# 7. Still in the home folder, run `sudo dictauth encrypt_password` and follow the on-screen instructions
# this will spit out a hash and a salt then do `sudo dictauth add_user --user tiffany --digest [the_big_hash_string] --salt [the_big_salt_string]`
# 
# 8. Now go in your web browser to www.your-jupyterhub.domain.com and you should see the login screen -- login with your username and password (make sure you can't login with another username and password).
# 
# 9. Go back and do the `sudo rudaux list` step and make sure that works
# 
# 10. Copy the cron script `rudaux/rudaux/cron/rudaux_manage` into `/etc/cron.d`, and make sure to fix the pathname to be your home folder with the rudaux config file
# 
# 11. Create a set of SSH keys to use to authenticate into the Instructor GitHub repository:
# 
#     ```
#     sudo su
#     cd /root/.ssh
#     vim id_rsa.pub
#     ```
# 
# 
#  12. Copy that public key to settings/deploy keys in whatever repo you want to give read access to (don't give it write  permission, no need for that). `rudaux` runs as root, so you need to look in root's user folder for the public key (no need to have multiple keys)
# 
# 13. Finally run `sudo rudaux run` on the command line in your home folder and it'll 1) give students an automatic extension for late reg assignments -- it will create overrides on canvas, and 2) run the autograding workflow for all submissions that are past due.

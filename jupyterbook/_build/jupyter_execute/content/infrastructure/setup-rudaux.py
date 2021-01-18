#!/usr/bin/env python
# coding: utf-8

# ## Setup NFS
# 
# We need to connect the student and grading servers via NFS so that the snapshotted student work can be copied to the grading server for grading. Student server is sharing a ZFS volume with grading server, so client is grading server.
# 
# Get the client (grading) server IP by ssh'ing on and typing: `ip addr show eth0` and you will get an output like this:
# 
# ```
# Last login: Thu Jan  7 20:11:00 2021 from 206.12.14.102
# [centos@dsci-100-instructor ~]$ ip addr show eth0
# 2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 9001 qdisc mq state UP group default qlen 1000
#     link/ether 02:5d:6f:37:03:a0 brd ff:ff:ff:ff:ff:ff
#     inet 222.32.32.222/22 brd 222.11.11.111 scope global dynamic eth0
#        valid_lft 3518sec preferred_lft 3518sec
#     inet6 fe80::5d:6fff:fe37:3a0/64 scope link 
#        valid_lft forever preferred_lft forever
# 
# ```
# 
# And the IP address is then `222.32.32.222/22`.
# 
# We then use that IP address in the command below **on the student server** to add a property called `sharenfs` on the `tank/home` filesystem:
# 
# ```
# sudo zfs set sharenfs='rw=@222.32.32.222/32,crossmnt,no_root_squash' tank/home
# ```
# 
# The "child" filesystems (e.g. `tank/home/dsci100`) will inherit this value (unless we override them, but we wont).
# 
# To check that this worked type: `zfs get sharenfs tank/home` and you should see something like:
# 
# ```
# NAME       PROPERTY  VALUE                                         SOURCE
# tank/home  sharenfs  rw=@222.32.32.222/32,crossmnt,no_root_squash  local
# ```
# 
# Next we need to start the NFS server via:
# 
# ```
# sudo systemctl enable rpcbind
# sudo systemctl enable nfs-server
# sudo systemctl start rpcbind
# sudo systemctl start nfs-server
# ```
# 
# From the student server, poke a hole through the firewall by typing:
# 
# ```
# firewall-cmd --permanent --zone=public --add-rich-rule='rule family="ipv4" source address="<GRADING_SERVER_IP>/32" port port="2049" protocol="tcp" accept'
# firewall-cmd --reload
# ```
# 
# Using the AWS console, edit the security groups of the student server to add NFS with Port 2049, and the grading IP /32.
# 
# Then on the grading server create a directory called: `/tank-student/home`, and then on the student server run `systemctl restart nfs-server`, and then on the grading server run `sudo mount -t nfs <STUDENT_SERVER_IP>:/tank/home /tank-student/home`.
# 
# Then on the grading server run the code below as a super user (`sudo su -`) to tell it to mount our NFS share after a reboot:
# 
# ```
# echo "<STUDENT_SERVER_IP>:/tank/home /tank-student/home nfs defaults 1 2" >> /etc/fstab
# ```

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
# 3. Install nbgrader & git via `sudo pip3 install nbgrader` and `sudo pip3 install gitpython`, and then go to `rudaux/dictauth` and type `sudo pip3 install . --upgrade`
# 
# 4. Fill out the template rudaux config in `rudaux/rudaux/scripts/rudaux_template_config.py` and put that in your home folder and rename it `rudaux_config.py`
# 
# 5. Add `rudaux` to the PATH for root and sudo user. To do this become the super user via `sudo su -` and then in HOME add `rudaux` to the PATH in `.bash_profile` via `export PATH="/usr/local/bin:$PATH"`, and then edit `/etc/sudoers` so that `/usr/local/bin/` is added to the  `secure_path` (it should read: `Defaults    secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin`).
# 
# 6. In the home folder run `sudo rudaux list`  -- this should successfully show you the list of students, tas, instructors, and Jupyterhub assignments
# 
# 7. Copy the cron job script `rudaux/rudaux/cron/rudaux_snapshot` into `/etc/cron.d/rudaux_snapshot`
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
# 4. Install nbgrader & git via `sudo pip3 install nbgrader` and `sudo pip3 install gitpython`, and then go to `rudaux/dictauth` and type `sudo pip3 install . --upgrade`
# 
# 5. Add `rudaux` to the PATH for root and sudo user. To do this become the super user via `sudo su -` and then in HOME add `rudaux` to the PATH in `.bash_profile` via `export PATH="/usr/local/bin:$PATH"`, and then edit `/etc/sudoers` so that `/usr/local/bin/` is added to the  `secure_path` (it should read: `Defaults    secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/usr/local/bin`).
# 
# 6. Open up your `/srv/jupyterhub/jupyterhub_config.py` file remove any LTAuthenticator lines and replace with 
#     ```
#     c.JupyterHub.authenticator_class = 'dictauth.DictionaryAuthenticator'
#     c.DictionaryAuthenticator.encrypted_passwords = {}
#     ```
#     
# 7. In the home folder, type `sudo dictauth list_users` -- should output an empty list
# 
# 8. Still in the home folder, run `sudo dictauth encrypt_password` and follow the on-screen instructions
# this will spit out a hash and a salt then do `sudo dictauth add_user --user tiffany --digest [the_big_hash_string] --salt [the_big_salt_string]`. Restart the JupyterHub: `sudo systemctl restart jupyterhub`.
# 
# 9. Now go in your web browser to www.your-jupyterhub.domain.com and you should see the login screen -- login with your username and password (make sure you can't login with another username and password).
# 
# 10. Go back and do the `sudo rudaux list` step and make sure that works
# 
# 11. Copy the cron script `rudaux/rudaux/cron/rudaux_manage` into `/etc/cron.d`, and make sure to fix the pathname to be your home folder with the rudaux config file
# 
# 12. Create a set of SSH keys to use to authenticate into the Instructor GitHub repository:
# 
#     ```
#     sudo su
#     cd /root/.ssh
#     ssh-keygen # do not add a passphrase
#     vim id_rsa.pub
#     ```
# 
# 
# 13. Copy that public key to settings/deploy keys in whatever repo you want to give read access to (don't give it write  permission, no need for that). `rudaux` runs as root, so you need to look in root's user folder for the public key (no need to have multiple keys)
# 
# 14. Finally run `sudo rudaux run` on the command line in your home folder and it'll 1) give students an automatic extension for late reg assignments -- it will create overrides on canvas, and 2) run the autograding workflow for all submissions that are past due.

# In[ ]:





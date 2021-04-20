# DictAuth

This package creates a dictionary-based authenticator for JupyterHub. 

- Make sure JupyterHub is installed and set up correctly. 
- run `sudo pip3 install .` in the current repository
- Then in your `jupyterhub_config.py` file,  set  
```
c.JupyterHub.authenticator_class = 'dictauth.DictionaryAuthenticator'
```

To list users in the JupyterHub, do
```
sudo dictauth list_users
```

The default location for the `jupyterhub_config.py` file is `/srv/jupyterhub/`, 
so if your file is not there you must specify it with the `--dir` option.

If you want to add a user to the JupyterHub, first have them install this package and run
```
dictauth encrypt_password
```
This will walk them through the process of generating a salt and a SHA512 digest of their salted password.
Then to add them to the JupyterHub, do
```
sudo dictauth add_user --user their_username --salt their_salt --digest their_digest
```

To remove a user from the JupyterHub authentication dictionary, do
```
sudo dictauth remove_user --user their_username
```

To make a user an admin (who can use their own password to log into any username), do
```
sudo dictauth make_admin --user their_username
```

To remove a user from the list of admins, do
```
sudo dictauth un_admin --user their_username
```

Make sure you restart your JupyterHub after these changes, e.g., with `sudo systemctl stop jupyterhub` and `sudo systemctl start jupyterhub`. 


import os
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import re

def list_users(directory):
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             There is no jupyterhub_config.py in the specified directory ({directory}). 
             Please specify a directory with a valid jupyterhub_config.py file. 
             """
           )
    config = Config()
    config.merge(PyFileConfigLoader('jupyterhub_config.py', path=directory).load_config())
    print(config.keys())

def _save_dict(epwrds, directory):
    #traitlets doesn't have a great way of writing PyFile configs back to disk, so we'll just do it manually
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'r') as f:
        lines = f.readlines()

    found_line = False
    for i in range(len(lines)):
        if 'c.DictionaryAuthenticator.encrypted_passwords' == lines[i][:45]:
            found_line = True
            lines[i] = 'c.DictionaryAuthenticator.encrypted_passwords = ' + str(epwrds) 
            break
    #if no line starting with this found, append a new one
    if not found_line:
        lines.append('c.DictionaryAuthenticator.encrypted_passwords = ' + str(epwrds) )
       
    #save the file
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'w') as f:
        f.writelines(lines)

def add_user(username, salt, digest, directory):
    #validate the salt + digest
    salt_digest_validator_regex = re.compile(r"^[a-f0-9]{128,}")
    if (not salt_digest_validator_regex.search(salt)) or (not salt_digest_validator_regex.search(digest)):
        sys.exit(
             f"""
             The salt or digest is not valid.
             Both the salt and digest must be a 128-character long string with characters from a-f and 0-9.
             Salt: {salt}
             Dgst: {digest}
             """
           )
    #check the config file exists
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             There is no jupyterhub_config.py in the specified directory ({directory}). 
             Please specify a directory with a valid jupyterhub_config.py file. 
             """
           )

    #load the config
    config = Config()
    config.merge(PyFileConfigLoader('jupyterhub_config.py', path=directory).load_config())
    epwrds = config.DictionaryAuthenticator.encrypted_passwords
    #if the user already exists (or if DictionaryAuthenticator.encrypted_passwords isn't in the file), error
    if epwrds.get(username):
        sys.exit(
             f"""
             There is already a user named {username} in the dictionary. Please
             remove them before creating a new user with this same username.  
             """
           )
    epwrds[username] = {'salt' : salt, 'digest' : digest}

    _save_dict(epwrds, directory)

def remove_user(username, directory):
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             There is no jupyterhub_config.py in the specified directory ({directory}). 
             Please specify a directory with a valid jupyterhub_config.py file. 
             """
           )
    config = Config()
    config.merge(PyFileConfigLoader('jupyterhub_config.py', path=directory).load_config())
    if not config.DictionaryAuthenticator.encrypted_passwords.get(username):
        sys.exit(
             f"""
             There is no user named {username} in the dictionary.   
             """
           )
    config.DictionaryAuthenticator.encrypted_passwords.pop(username, None)

    _save_dict(config.DictionaryAuthenticator.encrypted_passwords, directory)


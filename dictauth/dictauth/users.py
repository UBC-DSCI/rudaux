import os, sys
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
from tabulate import tabulate
import re


# TODO the _save and _load code here is largely repeated for user dict and admin list.
# try to avoid duplicated code

def _save_user_dict(epwrds, directory):
    #traitlets doesn't have a great way of writing PyFile configs back to disk, so we'll just do it manually
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'r') as f:
        lines = f.readlines()

    found_line = False
    for i in range(len(lines)):
        if 'c.DictionaryAuthenticator.encrypted_passwords' == lines[i][:45]:
            found_line = True
            lines[i] = 'c.DictionaryAuthenticator.encrypted_passwords = ' + str(epwrds) + '\n'
            break
    #if no line starting with this found, append a new one
    if not found_line:
        lines.append('c.DictionaryAuthenticator.encrypted_passwords = ' + str(epwrds) + '\n')

    #save the file
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'w') as f:
        f.writelines(lines)

def _load_user_dict(directory):
    #check the config file exists
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             ERROR: There is no jupyterhub_config.py in the specified directory ({directory}).
             Please specify a directory with a valid jupyterhub_config.py file.
             """
           )
    #load the config
    config = Config()
    config.merge(PyFileConfigLoader('jupyterhub_config.py', path=directory).load_config())
    if 'encrypted_passwords' in config.DictionaryAuthenticator:
        epwrds = config.DictionaryAuthenticator.encrypted_passwords
        if not isinstance(epwrds, dict):
            epwrds = epwrds.to_dict()
    else:
        print('Warning: jupyterhub_config.py does not have an entry for c.DictionaryAuthenticator.encrypted_passwords; continuing with empty dict')
        epwrds = {}
    return epwrds

def _save_admin_list(admins, directory):
    #traitlets doesn't have a great way of writing PyFile configs back to disk, so we'll just do it manually
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'r') as f:
        lines = f.readlines()

    found_line = False
    for i in range(len(lines)):
        if 'c.DictionaryAuthenticator.admins' == lines[i][:32]:
            found_line = True
            lines[i] = 'c.DictionaryAuthenticator.admins = ' + str(admins) + '\n'
            break
    #if no line starting with this found, append a new one
    if not found_line:
        lines.append('c.DictionaryAuthenticator.admins = ' + str(admins) + '\n')

    #save the file
    with open(os.path.join(directory, 'jupyterhub_config.py'), 'w') as f:
        f.writelines(lines)

def _load_admin_list(directory):
    #check the config file exists
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             ERROR: There is no jupyterhub_config.py in the specified directory ({directory}).
             Please specify a directory with a valid jupyterhub_config.py file.
             """
           )
    #load the config
    config = Config()
    config.merge(PyFileConfigLoader('jupyterhub_config.py', path=directory).load_config())
    if 'admins' in config.DictionaryAuthenticator:
        admins = config.DictionaryAuthenticator.admins
        if not isinstance(admins, list):
            admins = list(admins)
    else:
        print('Warning: jupyterhub_config.py does not have an entry for c.DictionaryAuthenticator.admins; continuing with empty list')
        admins = []
    return admins

def get_users(args):
    directory = args.directory
    if not os.path.exists(os.path.join(directory, 'jupyterhub_config.py')):
        sys.exit(
             f"""
             ERROR: There is no jupyterhub_config.py in the specified directory ({directory}).
             Please specify a directory with a valid jupyterhub_config.py file.
             """
           )
    admins = _load_admin_list(directory)
    epwrds = _load_user_dict(directory)
    users = []
    for unm in epwrds:
        # check if creds copied
        copied = None
        for user in users:
            if epwrds[unm]['digest'] == epwrds[user[0]]['digest'] and epwrds[unm]['salt'] == epwrds[user[0]]['salt']:
                # copied!
                copied = user[0]
                break
        users.append( (unm, 'admin' if unm in admins else 'user', copied) )
    return users

def list_users(args):
    users = get_users(args)
    print('Users')
    headers = ['Name', 'Type', 'Cred Copied']
    print(tabulate(users, headers=headers))
    print()

def add_user(args):
    username = args.username
    salt = args.salt
    digest = args.digest
    directory = args.directory
    user_creds_to_copy = args.copy_creds

    # prevent special characters in name
    if not username.isalnum():
        sys.exit(
                 f"""
                 ERROR: The username must have only alphanumeric characters.
                 Input Username: {username}
                 """
               )


    epwrds = None
    if user_creds_to_copy is None:
        #validate the salt + digest
        salt_digest_validator_regex = re.compile(r"^[a-f0-9]{128,}")
        if (not salt_digest_validator_regex.search(salt)) or (not salt_digest_validator_regex.search(digest)):
            sys.exit(
                 f"""
                 ERROR: The salt or digest is not valid.
                 Both the salt and digest must be a 128-character long string with characters from a-f and 0-9.
                 Input Salt: {salt}
                 Input Dgst: {digest}
                 """
               )

        epwrds = _load_user_dict(directory)

        #if the user already exists (or if DictionaryAuthenticator.encrypted_passwords isn't in the file), error
        if epwrds.get(username):
            sys.exit(
                 f"""
                 ERROR: There is already a user named {username} in the dictionary. Please
                 remove them before creating a new user with this same username.
                 """
               )
        epwrds[username] = {'salt' : salt, 'digest' : digest}
    else:
        epwrds = _load_user_dict(directory)
        if not epwrds.get(user_creds_to_copy):
            sys.exit(
                f"""
                ERROR: User {user_creds_to_copy} does not exist in the list of users.
                Cannot copy credentials. User {username} not created.
                """)
        #if the user already exists (or if DictionaryAuthenticator.encrypted_passwords isn't in the file), error
        if epwrds.get(username):
            sys.exit(
                 f"""
                 ERROR: There is already a user named {username} in the dictionary. Please
                 remove them before creating a new user with this same username.
                 """
               )
        epwrds[username] = {'salt' : epwrds[user_creds_to_copy]['salt'], 'digest' : epwrds[user_creds_to_copy]['digest']}

    _save_user_dict(epwrds, directory)



def remove_user(args):
    username = args.username
    directory = args.directory

    epwrds = _load_user_dict(directory)

    if not epwrds.get(username):
        sys.exit(
             f"""
             Warning: There is no user named {username} in the dictionary. Nothing changed.
             """
           )
    epwrds.pop(username, None)

    _save_user_dict(epwrds, directory)

def rename_user(args):
    username = args.username
    new_username = args.new_username
    directory = args.directory

    #first make sure the user exists and extract the salt/digest
    epwrds = _load_user_dict(directory)
    if not epwrds.get(username):
        sys.exit(
             f"""
             Warning: There is no user named {username} in the dictionary. Nothing changed.
             """
           )
    tmp = epwrds[username]

    #remove the old user, add the new one
    remove_user(args)
    args.salt = tmp['salt']
    args.digest = tmp['digest']
    args.username = args.new_username
    add_user(args)

def make_admin(args):
    username = args.username
    directory = args.directory
    admins = _load_admin_list(directory)
    epwrds = _load_user_dict(directory)

    if not epwrds.get(username):
        sys.exit(
             f"""
             There is no user named {username} in the dictionary.
             """
           )

    if username in admins:
        sys.exit(
             f"""
             User {username} is already in the list of admins.
             """
           )
    admins.append(username)

    _save_admin_list(admins, directory)

def un_admin(args):
    username = args.username
    directory = args.directory
    admins = _load_admin_list(directory)

    if username not in admins:
        sys.exit(
             f"""
             There is no user named {username} in the list of admins.
             """
           )
    admins.remove(username)

    _save_admin_list(admins, directory)

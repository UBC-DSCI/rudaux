from jupyterhub.auth import Authenticator
import hashlib
from traitlets import Dict, List, HasTraits

class DictionaryAuthenticator(Authenticator,HasTraits):

    encrypted_passwords = Dict(config=True,
        help="""dict of username -> {digest -> hashval, salt -> saltval} for authentication with SHA512"""
    )

    admins = List(config=True,
        help="""list of usernames that can use their own password to authenticate into any other user's account"""
    )


    def _password_valid(self, username, password):
        #get digest/salt for that username
        stored_digest = self.encrypted_passwords[username]['digest']
        salt = self.encrypted_passwords[username]['salt']
        #create the salted pw
        salted_pw_bytes = (password+salt).encode('utf-8')
        #hash the pw
        digest = hashlib.sha512(salted_pw_bytes).hexdigest()
        #if it matches, return username
        return digest == stored_digest

    async def authenticate(self, handler, data):
        #check if username is in whitelist
        if self.encrypted_passwords.get(data['username']):
            # if the password matches the username, authenticate
            if self._password_valid(data['username'], data['password']):
                return data['username']
            # if not, see if the password matches the pword of any of the admin users
            for admin_user in self.admins:
                if self._password_valid(admin_user, data['password']):
                    return data['username']

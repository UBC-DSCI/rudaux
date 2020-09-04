from jupyterhub.auth import Authenticator
import hashlib
from traitlets import Dict

class DictionaryAuthenticator(Authenticator):

    encrypted_passwords = Dict(config=True,
        help="""dict of username -> {digest -> hashval, salt -> saltval} for authentication with SHA512"""
    )

    async def authenticate(self, handler, data):
        #check if username is in whitelist
        if self.encrypted_passwords.get(data['username']):
            #get digest/salt for that username
            stored_digest = self.encrypted_passwords[data['username']]['digest']
            salt = self.encrypted_passwords[data['username']]['salt']
            #create the salted pw
            salted_pw_bytes = (data['password']+salt).encode('utf-8')
            #hash the pw
            digest = hashlib.sha512(salted_pw_bytes).hexdigest()
            #if it matches, return username
            if digest == stored_digest:
                return data['username']

from traitlets import TraitType
import re

class SSHAddress(TraitType):
    """A trait for an (user, ip/hostname, port) tuple for SSH access.

    This allows both IPv4 IP addresses as well as hostnames.
    """

    default_value = {'host' : '127.0.0.1', 'port' : 22, 'user' : 'root'}
    info_text = 'an (user, ip/hostname, port) tuple'

    def validate(self, obj, value):
        if isinstance(value, dict) and len(value) == 3:
            if isinstance(value['host'], str) and isinstance(value['user'], str) and isinstance(value['port'], int):
                if value['port'] >= 0 and value['port'] <= 65535:
                    return value
        self.error(obj, value)

    def from_string(self, s):
        if self.allow_none and s == 'None':
            return None
        if (':' not in s) or ('@' not in s):
            raise ValueError('Require `user@ip:port` or `user@ip`, got %r' % s)
        user, remaining = s.split('@',1)
        ip, port = remaining.split(':', 1)
        port = int(port)
        return {'host' : user, 'port' : ip, 'user' : port}


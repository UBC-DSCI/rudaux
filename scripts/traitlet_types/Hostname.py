from traitlets.config.configurable import Configurable, SingletonConfigurable
from traitlets import Int, Float, Unicode, Bool, TraitType
import re
from sphinx.util.typing import NoneType


class Hostname(TraitType):
    """A trait for hostnames
    """
#https://canvas.instructure.com/
#https://canvas.ubc.ca
    default_value = 'https://canvas.instructure.com/'
    info_text = 'base url for canvas course'

    def validate(self, obj, value):
        if re.match("https:\/\/canvas.((instructure.com)|(ubc.ca))", value) is not None:
            return value
        self.error(obj, value)


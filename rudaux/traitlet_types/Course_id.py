from traitlets.config.configurable import Configurable, SingletonConfigurable
from traitlets import Int, Float, Unicode, Bool
from traitlets import TraitType
import re
from sphinx.util.typing import NoneType


class Course_id(TraitType):
    """A trait for Course_id
    """
    info_text = 'course number. for example, course number for this course https://canvas.instructure.com/courses/2039048 would be 2039048'

    def validate(self, obj, value):
        if re.match("^([0-9]){4,}$", value) is not None:
            return int(value)
        self.error(obj, value)


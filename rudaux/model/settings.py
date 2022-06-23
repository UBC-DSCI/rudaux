from typing import Dict, Type
from pydantic import BaseModel

class Settings(BaseModel):
    # map of course_group to list of course names in that group
    course_groups : Dict[str, List[str]]
    # maps course_group to LMS, GMS, SMS class type
    lms_classes : Dict[str, Type]
    gms_classes : Dict[str, Type]
    sms_classes : Dict[str, Type]


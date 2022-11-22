import pendulum as plm
from typing import Optional, List, Dict
from pydantic import BaseModel
from .course_section_info import CourseSectionInfo
from .student import Student


class Override(BaseModel):
    lms_id: str
    name: Optional[str] = None
    due_at: plm.DateTime
    lock_at: plm.DateTime
    unlock_at: plm.DateTime
    students: Dict[str, Student]
    course_section_info: CourseSectionInfo

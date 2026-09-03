import pendulum as plm
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from .course_section_info import CourseSectionInfo
from .student import Student


class Override(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    name: Optional[str] = None
    due_at: plm.DateTime | None
    lock_at: plm.DateTime | None
    unlock_at: plm.DateTime | None
    students: Dict[str, Student] | None
    course_section_id: str | None
    course_section_info: CourseSectionInfo
    assignment_id: str

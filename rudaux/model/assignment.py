import pendulum as plm
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from .override import Override
from .course_section_info import CourseSectionInfo


class Assignment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    name: str
    due_at: plm.DateTime | None
    lock_at: plm.DateTime | None
    unlock_at: plm.DateTime | None
    overrides: Dict[str, Override]
    only_visible_to_overrides: bool
    published: bool
    course_section_info: CourseSectionInfo
    skip: bool

import pendulum as plm
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict
from rudaux.model.course_section_info import CourseSectionInfo
from rudaux.model.grader import Grader
from rudaux.model.student import Student
from rudaux.model.assignment import Assignment


class Submission(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    student: Student
    assignment: Assignment
    score: float | None
    posted_at: plm.DateTime | None
    late: bool
    missing: bool
    excused: bool
    course_section_info: CourseSectionInfo
    grader: Optional[Grader]
    status: int
    skip: bool



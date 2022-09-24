import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel
from rudaux.model.student import Student
from rudaux.model.assignment import Assignment


class Submission(BaseModel):
    lms_id: str
    student: Student
    assignment: Assignment
    score: int
    posted_at: plm.DateTime
    late: bool
    missing: bool
    excused: bool



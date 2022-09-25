import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel
from .override import Override
from .student import Student
from .assignment import Assignment


class Snapshot(BaseModel):
    assignment : Assignment
    override : Optional[Override]
    student : Optional[Student]
    name : str

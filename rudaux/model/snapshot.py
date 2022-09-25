import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel
from .override import Override
from .student import Student
from .assignment import Assignment

def parse_snapshot_name(snap_name, assignments, students):
    tokens = snap_name.split("-")
    info = {}
    info["course_name"] = tokens[0]
    info["assignment"] = assignments[tokens[1]]
    if len(tokens) > 3:
        info["override"] = assignments[tokens[1]].overrides[tokens[3]]
        info["student"] = assignments[tokens[1]].overrides[tokens[3]].students[tokens[5]]
    else:
        info["override"] = None
        info["student"] = None
    return Snapshot.parse_obj(info)
     
class Snapshot(BaseModel):
    course_name : str
    assignment : Assignment
    override : Optional[Override]
    student : Optional[Student]

    def get_name(self):
        return f"{self.course_name}-{self.assignment.name}-{self.assignment.lms_id}" + \
			("" if override is None else f"-{self.override.name}-{self.override.lms_id}-{self.student.name}-{self.student.lms_id}")

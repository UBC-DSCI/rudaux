import pendulum as plm
from typing import Optional, List, Dict
from pydantic import BaseModel
from .override import Override
from .student import Student
from .assignment import Assignment


def parse_snapshot_from_name(snap_name: str, assignments: Dict[str, Assignment]):
    # snap_name format = '{course_name}-{section_number}-{assignment_name}-{student_lms_is}-{override_lms_id}'
    # example: tank/home/stat301/868424@stat301-101-worksheet_01-1338692-242114

    # if there is override:
    #     f"rudaux--{self.course_name}--{self.assignment.name}--{self.assignment.lms_id}--{self.override.name}
    #     --{self.override.lms_id}--{self.student.name}--{self.student.lms_id}
    #     "
    # if there is no override:
    #     f"rudaux--{self.course_name}--{self.assignment.name}--{self.assignment.lms_id}"

    tokens = snap_name.split("--")

    if tokens[0] == 'rudaux':
        course_name = tokens[1]
        assignment_name = tokens[2]
        assignment_lms_id = tokens[3]

        info = dict()
        info["course_name"] = course_name
        info["assignment"] = assignments[assignment_lms_id]
        info["override"] = None
        info["student"] = None

        if len(tokens) > 4:
            override_name = tokens[4]
            override_lms_id = tokens[5]
            student_name = tokens[6]
            student_lms_id = tokens[7]

            info["override"] = assignments[assignment_lms_id].overrides[override_lms_id]
            info["student"] = assignments[assignment_lms_id].overrides[override_lms_id].students[student_lms_id]

        snapshot = Snapshot.parse_obj(info)
        return snapshot


class Snapshot(BaseModel):
    course_name: str
    assignment: Assignment
    override: Optional[Override]
    student: Optional[Student]

    def get_name(self) -> str:
        """
        if there is override:
            f"{self.course_name}--{self.assignment.name}--{self.assignment.lms_id}--{self.override.name}-
                {self.override.lms_id}--{self.student.name}--{self.student.lms_id}"
        if there is no override:
            f"{self.course_name}--{self.assignment.name}--{self.assignment.lms_id}"

        Returns
        -------
        snapshot_name: str
        """

        snapshot_name = f"rudaux--{self.course_name}--{self.assignment.name}--{self.assignment.lms_id}" + \
                        ("" if self.override is None else f"--{self.override.name}--{self.override.lms_id}"
                                                          f"--{self.student.name}--{self.student.lms_id}")

        # replacing all spaces with underscore in the name
        snapshot_name = snapshot_name.replace(' ', '_')
        return snapshot_name

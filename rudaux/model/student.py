import pendulum as plm
from pydantic import BaseModel, ConfigDict


class Student(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    name: str
    sortable_name: str
    school_id: str | None
    reg_date: plm.DateTime
    status: str

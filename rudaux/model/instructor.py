import pendulum as plm
from pydantic import BaseModel, ConfigDict


class Instructor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    name: str
    sortable_name: str
    school_id: str
    reg_date: plm.DateTime
    status: str

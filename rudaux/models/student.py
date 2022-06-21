import pendulum as plm
from pydantic import BaseModel

class Student(BaseModel):
    lms_id : str
    name : str
    sortable_name : str
    school_id : str
    reg_date : plm.DateTime
    status : str

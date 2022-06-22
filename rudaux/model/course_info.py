import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel

class CourseInfo(BaseModel):

    lms_id : str
    name : str
    code : str
    start_at : plm.DateTime
    end_at : plm.DateTime
    time_zone : str


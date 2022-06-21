import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel

class Override(BaseModel):
    lms_id : str
    name : Optional[str] = None
    due_at : plm.DateTime
    lock_at : plm.DateTime
    unlock_at : plm.DateTime
    students : List[Student]

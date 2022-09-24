import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel
from .override import Override


class Assignment(BaseModel):
    lms_id: str
    name: str
    due_at: Optional[plm.DateTime]
    lock_at: Optional[plm.DateTime]
    unlock_at: Optional[plm.DateTime]
    overrides: Optional[List[Override]]
    published: bool

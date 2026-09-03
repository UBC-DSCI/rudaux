import pendulum as plm
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class CourseSectionInfo(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    lms_id: str
    name: str
    code: str
    start_at: plm.DateTime | None
    end_at: plm.DateTime | None
    time_zone: str

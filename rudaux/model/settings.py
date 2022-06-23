from typing import Dict, Type, List
from pydantic import BaseModel

class Settings(BaseModel):
    # various constants
    prefect_queue_name : str = "rudaux-queue"
    prefect_deployment_prefix : str = "rudaux-deployment-"
    autoext_prefix : str = "autoext-"
    autoext_cron_string : str = "1,16,31,46 * * * *"
    # map of course_group to list of course names in that group
    course_groups : Dict[str, List[str]]
    # maps course_group to LMS, GMS, SMS class type
    #lms_classes : Dict[str, Type]
    #gms_classes : Dict[str, Type]
    #sms_classes : Dict[str, Type]


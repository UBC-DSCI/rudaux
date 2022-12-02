from typing import Dict, List, Optional
from pydantic import BaseModel, validator
import importlib


class Settings(BaseModel):

    # various constants
    prefect_queue_name: str = "rudaux-queue"
    prefect_deployment_prefix: str = "rudaux-deployment-"
    autoext_prefix: str = "autoext-"
    autoext_cron_string: str = "1,31 * * * *"
    snap_prefix: str = "snap-"
    snap_cron_string: str = "1,16,31,46 * * * *"
    grade_prefix: str = "grade-"
    grade_cron_string: str = "0 23 * * *"
    soln_prefix: str = "soln-"
    soln_cron_string: str = "30 23 * * *"
    fdbk_prefix: str = "fdbk-"
    fdbk_cron_string: str = "45 23 * * *"

    # map of course_group to list of course names in that group
    course_groups: Dict[str, List[str]]

    # maps course_group to LMS, GMS, SMS class type
    lms_classes: Dict[str, str]
    gs_classes: Dict[str, str]
    ss_classes: Dict[str, str]

    # canvas settings
    canvas_base_domain: str
    canvas_course_lms_ids: Dict[str, str]
    canvas_registration_deadlines: Dict[str, str]
    canvas_api_tokens: Dict[str, str]
    assignments: Dict[str, dict]
    latereg_extension_days: Dict[str, int]
    notify_timezone: Dict[str, str]

    # zfs settings
    remote_zfs_hostname: Dict[str, str]
    remote_zfs_port: Dict[str, str]
    remote_zfs_username: Dict[str, str]
    remote_zfs_tz: Dict[str, str]
    # remote_zfs_volume_pattern: str
    # remote_zfs_collection_pattern: str
    # remote_zfs_distribution_pattern: str
    remote_zfs_file_system_root: Dict[str, str]

    # nbgrader settings
    nbgrader_docker_image: str
    nbgrader_docker_memory: str
    nbgrader_docker_bind_folder: str
    nbgrader_student_folder_prefix: str
    nbgrader_instructor_user: str
    nbgrader_jupyterhub_config_dir: str
    nbgrader_jupyterhub_user: str
    nbgrader_jupyterhub_group: str
    nbgrader_user_quota: str
    nbgrader_user_root: str
    nbgrader_submissions_folder: Optional[str] = 'submitted'
    nbgrader_feedback_folder: Optional[str] = 'feedback'
    nbgrader_autograded_folder: Optional[str] = 'autograded'

    instructor_repo_url: str
    student_local_assignment_folder: str
    return_solution_threshold: float
    earliest_solution_return_date: str

from prefect import task
import importlib
from .interface import LearningManagementSystem, GradingSystem, SubmissionSystem

def get_class_from_string(s):
    module_name, class_name = s.rsplit(".", 1)
    return getattr(importlib.import_module(module_name), class_name)

@task
def get_learning_management_system(settings, config_path, group_name):
    LMS = get_class_from_string(settings.lms_classes[group_name])
    if not issubclass(LMS, LearningManagementSystem):
        raise ValueError
    return LMS.parse_file(config_path)

@task
def get_grading_system(settings, config_path, group_name):
    GrdS = get_class_from_string(settings.gms_classes[group_name])
    if not issubclass(GrdS, GradingSystem):
        raise ValueError
    return GrdS.parse_file(config_path)

@task
def get_submission_system(settings, config_path, group_name):
    SubS = get_class_from_string(settings.sms_classes[group_name])
    if not issubclass(SubS, SubmissionSystem):
        raise ValueError
    return SubS.parse_file(config_path)


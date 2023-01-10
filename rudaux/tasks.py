from prefect import task
import importlib
from .interface import LearningManagementSystem, GradingSystem, SubmissionSystem


def get_class_from_string(s):
    module_name, class_name = s.rsplit(".", 1)
    return getattr(importlib.import_module(module_name), class_name)


# @task
def get_learning_management_system(settings, group_name):
    LMS = get_class_from_string(settings.lms_classes[group_name])
    if not issubclass(LMS, LearningManagementSystem):
        raise ValueError
    lms = LMS.parse_obj(settings)
    # TODO any additional runtime validation (e.g. check if all assignments for all courses in group are the same, etc)
    return lms


# @task
def get_grading_system(settings, group_name):
    GrdS = get_class_from_string(settings.gs_classes[group_name])
    if not issubclass(GrdS, GradingSystem):
        raise ValueError
    grds = GrdS.parse_obj(settings)
    # TODO any additional runtime validation
    return grds


# @task
def get_submission_system(settings, group_name):
    SubS = get_class_from_string(settings.ss_classes[group_name])
    if not issubclass(SubS, SubmissionSystem):
        raise ValueError
    subs = SubS.parse_obj(settings)
    # TODO any additional runtime validation
    return subs

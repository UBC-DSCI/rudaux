import os
import sys
import yaml
from prefect import flow
# from prefect.flow_runners.subprocess import SubprocessFlowRunner
# from prefect.blocks.storage import TempStorageBlock
from prefect.client import get_client
from prefect.deployments import Deployment
from prefect.orion.schemas.schedules import CronSchedule

from rudaux.model import Settings
from rudaux.task.autoext import compute_autoextension_override_updates
from rudaux.task.grade import build_grading_team, initialize_volumes, initialize_accounts
from rudaux.task.submission import assign_graders, collect_submissions, clean_submissions, autograde, \
    check_manual_grading
from rudaux.tasks import get_learning_management_system, get_grading_system, get_submission_system
from rudaux.task.learning_management_system import get_students, get_assignments, get_submissions, \
    get_course_section_info, update_override, create_overrides, delete_overrides

from rudaux.task.snap import get_pastdue_snapshots, get_existing_snapshots, \
    get_snapshots_to_take, take_snapshots, verify_snapshots


# -------------------------------------------------------------------------------------------------------------
def load_settings(path):
    # load settings from the config
    print(f"Loading the rudaux configuration file {path}...")
    if not os.path.exists(path):
        sys.exit(
            f"""
              There is no configuration file at {path},
              and no other file was specified on the command line. Please
              specify a valid configuration file path.
              """
        )
    else:
        with open(path) as f:
            config = yaml.safe_load(f)

    return Settings.parse_obj(obj=config)


# -------------------------------------------------------------------------------------------------------------
async def run(args):
    # load settings from the config
    settings = load_settings(args.config_path)
    # start the prefect agent
    os.system(f"prefect agent start --work-queue {settings.prefect_queue_name}")


# -------------------------------------------------------------------------------------------------------------
async def register(args):
    # load settings from the config
    settings = load_settings(args.config_path)

    # start the client
    async with get_client() as client:
        # remove old rudaux deployments
        current_deployments = await client.read_deployments()
        for deployment in current_deployments:
            if settings.prefect_deployment_prefix in deployment.name:
                await client.delete_deployment(deployment.id)

        deployment_ids = []

        per_section_flows = [
            # (autoext_flow, settings.autoext_prefix, settings.autoext_cron_string),
            (snap_flow, settings.snap_prefix, settings.snap_cron_string)
        ]

        per_course_flows = [
            # (grade_flow, settings.grade_prefix, settings.grade_cron_string),
            # (soln_flow, settings.soln_prefix, settings.soln_cron_string),
            # (fdbk_flow, settings.fdbk_prefix, settings.fdbk_cron_string)
        ]

        for course_name in settings.course_groups:
            # -------------------------------------------------------------------------------------------------
            # building deployments for course groups
            for fl, prefix, cron in per_course_flows:
                name = settings.prefect_deployment_prefix + prefix + course_name

                deployment = await Deployment.build_from_flow(
                    flow=fl,
                    name=name,
                    work_queue_name=settings.prefect_queue_name,
                    schedule=CronSchedule(cron=cron, timezone="America/Vancouver"),
                    parameters={'settings': settings.dict(), 'course_name': course_name},
                )
                print(deployment)
                print('\n')
                deployment_id = await deployment.apply()
                deployment_ids.append(deployment_id)

            # -------------------------------------------------------------------------------------------------
            # building deployments for course sections
            for section_name in settings.course_groups[course_name]:
                for fl, prefix, cron in per_section_flows:
                    name = settings.prefect_deployment_prefix + prefix + section_name

                    deployment = await Deployment.build_from_flow(
                        flow=fl,
                        name=name,
                        work_queue_name=settings.prefect_queue_name,
                        schedule=CronSchedule(cron=cron, timezone="America/Vancouver"),
                        parameters={'settings': settings.dict(),
                                    'course_name': course_name, 'section_name': section_name},
                    )
                    print(deployment)
                    print('\n')
                    deployment_id = await deployment.apply()
                    deployment_ids.append(deployment_id)

            # -------------------------------------------------------------------------------------------------
        print("Flows registered.")
    return


# -------------------------------------------------------------------------------------------------------------
@flow
def autoext_flow(settings: dict, course_name: str, section_name: str) -> None:
    """
    applies extension overrides for certain students

    Parameters
    ----------
    settings: dict
    course_name: str
    section_name: str
    """

    # settings object was serialized by prefect when registering the flow, so need to reparse it
    settings = Settings.parse_obj(settings)

    # Create an LMS object
    lms = get_learning_management_system(settings=settings, group_name=course_name)

    # Get course info, list of students, and list of assignments from lms
    course_section_info = get_course_section_info(lms=lms, course_section_name=section_name)
    students = get_students(lms=lms, course_section_name=section_name)
    assignments = get_assignments(lms=lms, course_group_name=course_name,
                                  course_section_name=section_name)

    # Compute the set of overrides to delete and new ones to create
    # we formulate override updates as delete first, wait, then create to avoid concurrency issues
    # TODO map over assignments here (still fine with concurrency)

    # compute the set of overrides to delete and new ones to create for all assignments
    overrides = compute_autoextension_override_updates(
        settings=settings, course_name=course_name, section_name=section_name,
        course_info=course_section_info, students=students, assignments=assignments)

    # for each assignment remove the old overrides and create new ones
    for assignment, overrides_to_create, overrides_to_delete in overrides:
        # if overrides_to_delete is not None:
        delete_response = delete_overrides(lms=lms, course_section_name=section_name,
                                           assignment=assignment, overrides=overrides_to_delete)

        # if overrides_to_create is not None:
        create_response = create_overrides(lms=lms, course_section_name=section_name,
                                           assignment=assignment, overrides=overrides_to_create,
                                           wait_for=[delete_response])


# -------------------------------------------------------------------------------------------------------------
@flow
def snap_flow(settings: dict, course_name: str, section_name: str) -> None:
    """
    does the following;
    - computes the snapshots to be taken
    - gets all existing snapshots and identifies the ones which are not already taken and need to be taken
    - validates whether the snapshots to be taken were in fact taken

    Parameters
    ----------
    settings: dict
    course_name: str
    section_name: str
    """

    # settings object was serialized by prefect when registering the flow, so need to reparse it
    settings = Settings.parse_obj(settings)

    # Create an LMS and SubS object
    lms = get_learning_management_system(settings=settings, group_name=course_name)
    subs = get_submission_system(settings=settings, group_name=course_name)

    # initiate the submission system (open ssh connection)
    subs.open(course_name=course_name)

    # Get course info, list of students, and list of assignments from lms
    course_section_info = get_course_section_info(lms=lms, course_section_name=section_name)
    students = get_students(lms=lms, course_section_name=section_name)
    assignments = get_assignments(lms=lms, course_group_name=course_name, course_section_name=section_name)

    # get list of snapshots past their due date from assignments
    pastdue_snaps = get_pastdue_snapshots(
        course_name=course_name, course_info=course_section_info, assignments=assignments)

    # get list of existing snapshots from submission system
    existing_snaps = get_existing_snapshots(course_name=course_name, assignments=assignments,
                                            students=students, subs=subs)

    # compute snapshots to take
    snaps_to_take = get_snapshots_to_take(pastdue_snaps=pastdue_snaps, existing_snaps=existing_snaps)

    # take snapshots
    take_snapshots(course_name=course_name, snaps_to_take=snaps_to_take, subs=subs)

    # get list of newly existing snapshots from submission system
    new_existing_snaps = get_existing_snapshots(course_name=course_name, assignments=assignments,
                                                students=students, subs=subs)

    # verify snapshots
    verify_snapshots(snaps_to_take=snaps_to_take, new_existing_snaps=new_existing_snaps)

    subs.close()


# -------------------------------------------------------------------------------------------------------------
@flow
def grade_flow(settings: dict, course_name: str):
    settings = Settings.parse_obj(settings)

    # Create an LMS, SubS, and GradS objects
    lms = get_learning_management_system(settings=settings, group_name=course_name)
    subs = get_submission_system(settings=settings, group_name=course_name)
    grds = get_grading_system(settings=settings, group_name=course_name)

    course_section_names = settings.course_groups[course_name]
    selected_assignments = settings.assignments[course_name]

    # meta_assignments is a dict of unique assignment names as keys and
    # their list of assignment objects from different sections as values
    meta_assignments = dict()
    for section_name in course_section_names:
        # Get course info, list of students, and list of assignments from lms
        # course_section_info = get_course_section_info(lms=lms, course_section_name=section_name)
        # students = get_students(lms=lms, course_section_name=section_name)
        section_assignments = get_assignments(
            lms=lms, course_group_name=course_name, course_section_name=section_name)

        for section_assignment_id, section_assignment in section_assignments.items():
            if section_assignment.name not in meta_assignments:
                meta_assignments[section_assignment.name] = []
                meta_assignments[section_assignment.name].append(section_assignment)
            else:
                meta_assignments[section_assignment.name].append(section_assignment)

    for assignment_name, section_assignment_objects in meta_assignments.items():
        if assignment_name in selected_assignments:

            assignment_submissions_pairs = []
            for section_assignment in section_assignment_objects:
                section_submissions = get_submissions(
                    lms=lms, course_group_name=course_name,
                    course_section_name=section_assignment.course_section_info.name,
                    assignment=section_assignment
                )
                assignment_submissions_pairs.append((section_assignment, section_submissions))

            # Create grader teams
            graders = build_grading_team(settings=settings, grading_system=grds, course_group=course_name,
                                         assignment_name=assignment_name,
                                         assignment_submissions_pairs=assignment_submissions_pairs)

            # create grader volumes, add git repos, create folder structures, initialize nbgrader
            initialize_volumes(settings=settings, grading_system=grds, graders=graders)

            # create grader jhub accounts
            initialize_accounts(config=settings, graders=graders)

            # assign graders
            submission_sets = assign_graders(graders=graders,
                                             assignment_submissions_pairs=assignment_submissions_pairs)

            # compute the fraction of submissions past due for each assignment,
            # and then return solutions for all assignments past the threshold
            # pastdue_fractions = get_pastdue_fraction(submission_sets)

            # collect submissions
            collect_submissions()

            # clean submissions
            clean_submissions()

            # Autograde submissions
            autograde()

            # Wait for manual grading
            check_manual_grading()

            # Collect grading notifications
            # Skip assignments with incomplete manual grading
            # generate & return feedback
            # Upload grades
            # collect posting notifications


# -------------------------------------------------------------------------------------------------------------
@flow
def soln_flow(settings: dict, course_name: str):
    settings = Settings.parse_obj(settings)


# -------------------------------------------------------------------------------------------------------------
@flow
def fdbk_flow(settings: dict, course_name: str):
    settings = Settings.parse_obj(settings)


# -------------------------------------------------------------------------------------------------------------
async def list_course_info(args):
    # load settings from the config
    settings = load_settings(args.config_path)
    for course_name in settings.course_groups:
        lms = get_learning_management_system(settings, course_name)
        pass  # TODO

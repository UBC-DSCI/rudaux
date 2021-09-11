import sys, os
import prefect
from prefect import Flow, unmapped, task, flatten
from prefect.engine import signals
from prefect.schedules import IntervalSchedule
from prefect.executors import LocalExecutor, DaskExecutor, LocalDaskExecutor
from prefect.backend import FlowView, FlowRunView
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pendulum as plm
from requests.exceptions import ConnectionError
import logging

import threading

from . import snapshot as snap
from . import submission as subm
from . import course_api as api
from . import grader as grd
from . import notification as ntfy

__PROJECT_NAME = "rudaux"

def _build_flows(args):
    print("Loading the rudaux_config.py file...")
    if not os.path.exists(os.path.join(args.directory, 'rudaux_config.py')):
            sys.exit(
              f"""
              There is no rudaux_config.py in the directory {args.directory},
              and no course directory was specified on the command line. Please
              specify a directory with a valid rudaux_config.py file.
              """
            )
    config = Config()
    config.merge(PyFileConfigLoader('rudaux_config.py', path=args.directory).load_config())

    # validate the config file
    print("Validating the config file...")
    api.validate_config(config)
    snap.validate_config(config)
    subm.validate_config(config)
    grd.validate_config(config)
    ntfy.validate_config(config)

    print("Creating the executor")
    executor = LocalExecutor()
    # LocalDaskExecutor(num_workers = args.dask_threads)
    # for DaskExecutor: cluster_kwargs = {'n_workers': 8}) #address="tcp://localhost:8786")

    flow_builders = []
    if args.snap or args.all_flows:
        flow_builders.append((build_snapshot_flows, 'snapshot', args.snapshot_interval))
    if args.autoext or args.all_flows:
        flow_builders.append((build_autoext_flows, 'autoextension', args.autoext_interval))
    if args.grade or args.all_flows:
        flow_builders.append((build_grading_flows, 'grading', args.grading_interval))

    flows = []
    for build_func, flow_name, interval in flow_builders:
        print(f"Building/registering the {flow_name} flow...")
        _flows = build_func(config, args)
        for flow in _flows:
            flow.executor = executor
            flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                   interval = plm.duration(minutes=interval))
            flows.append(flow)
    return flows

def register(args):
    print("Creating/running flows via server orchestration")
    try:
        print(f"Creating the {__PROJECT_NAME} prefect project...")
        prefect.client.client.Client().create_project(__PROJECT_NAME)
    except ConnectionError as e:
        print(e)
        sys.exit(
              f"""
              Could not connect to the prefect server. Is the server running?
              Make sure to start the server before trying to register flows.
              To start the prefect server, run the command:

              prefect server start

              """
            )
    flows = _build_flows(args)
    for flow in flows:
        flow.register(__PROJECT_NAME)
    return

def _run_flow(flow):
    print(f"Flow {flow.name} starting...")
    flow.run()
    print(f"Flow {flow.name} stopping...")
    return

def run(args):
    print("Creating/running flows in local threads")
    flows = _build_flows(args)
    threads = []
    for flow in flows:
        threads.append(threading.Thread(name=flow.name, target=_run_flow, args=(flow,)))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    return

def build_snapshot_flows(config, args):
    flows = []
    for group in config.course_groups:
        for course_id in config.course_groups[group]:
            with Flow(config.course_names[course_id]+"-snap") as flow:
                # Obtain course/student/assignment/etc info from the course API
                course_info = api.get_course_info(config, course_id)
                assignments = api.get_assignments(config, course_id, list(config.assignments[group].keys()))

                # extract the total list of snapshots to take from assignment data
                snaps = snap.get_all_snapshots(config, course_id, assignments)

                # obtain the list of existing snapshots
                existing_snaps = snap.get_existing_snapshots(config, course_id)

                # take new snapshots
                snap.take_snapshot.map(unmapped(config), unmapped(course_info), snaps, unmapped(existing_snaps))
            flows.append(flow)
    return flows

@task(checkpoint=False)
def combine_dictionaries(dicts):
    return {k : v for d in dicts for k, v in d.items()}

def build_autoext_flows(config, args):
    flows = []
    for group in config.course_groups:
        for course_id in config.course_groups[group]:
            with Flow(config.course_names[course_id]+"-autoext") as flow:
                assignment_names = list(config.assignments[group].keys())
                # Obtain course/student/assignment/etc info from the course API
                course_info = api.get_course_info(config, course_id)
                assignments = api.get_assignments(config, course_id, assignment_names)
                students = api.get_students(config, course_id)
                submission_info = combine_dictionaries(api.get_submissions.map(unmapped(config), unmapped(course_id), assignments))

                # Create submissions
                submission_sets = subm.initialize_submission_sets(config, [course_info], [assignments], [students], [submission_info])

                # Fill in submission deadlines
                submission_sets = subm.build_submission_set.map(unmapped(config), submission_sets)

                # Compute override updates
                overrides = subm.get_latereg_overrides.map(unmapped(config.latereg_extension_days[group]), submission_sets)

                # TODO: we would ideally do flatten(overrides) and then
                # api.update_override.map(unmapped(config), unmapped(course_id), flatten(overrides))
                # but that will cause prefect to fail. see https://github.com/PrefectHQ/prefect/issues/4084
                # so instead we will code a temporary hack for update_override.
                api.update_override_flatten.map(unmapped(config), unmapped(course_id), overrides)

            flows.append(flow)
    return flows


# this creates one flow per grading group,
# not one flow per assignment. In the future we might
# not load assignments/graders from the rudaux config but
# rather dynamically from LMS; there we dont know what
# assignments there are until runtime. So doing it by group is the
# right strategy.
def build_grading_flows(config, args):
    flows = []
    for group in config.course_groups:
        with Flow(group+"-grading") as flow:
            # get the course ids in this group
            course_ids = config.course_groups[group]
            assignment_names = list(config.assignments[group].keys())

            # Obtain course/student/assignment/etc info from the course API
            course_infos = api.get_course_info.map(unmapped(config), course_ids)
            assignment_lists = api.get_assignments.map(unmapped(config), course_ids, unmapped(assignment_names))
            student_lists = api.get_students.map(unmapped(config), course_ids)
            submission_infos = []
            for i in range(len(course_ids)):
                submission_infos.append(combine_dictionaries(api.get_submissions.map(unmapped(config), unmapped(course_ids[i]), assignment_lists[i])))

            # Create submissions
            submission_sets = subm.initialize_submission_sets(unmapped(config), course_infos, assignment_lists, student_lists, submission_infos)

            # Fill in submission details
            submission_sets = subm.build_submission_set.map(unmapped(config), submission_sets)

            # Create grader teams
            grader_teams = grd.build_grading_team.map(unmapped(config), unmapped(group), submission_sets)

            # create grader volumes, add git repos, create folder structures, initialize nbgrader
            grader_teams = grd.initialize_volumes.map(unmapped(config), grader_teams)

            # create grader jhub accounts
            grader_teams = grd.initialize_accounts.map(unmapped(config), grader_teams)

            # assign graders
            submission_sets = subm.assign_graders.map(submission_sets, grader_teams)

            # compute the fraction of submissions past due for each assignment,
            # and then return solutions for all assignments past the threshold
            pastdue_fracs = subm.get_pastdue_fraction.map(submission_sets)
            subm.return_solutions.map(unmapped(config), pastdue_fracs, submission_sets)

            ## collect submissions
            submission_sets = subm.collect_submissions.map(unmapped(config), submission_sets)

            ## clean submissions
            submission_sets = subm.clean_submissions.map(submission_sets)

            ## Autograde submissions
            submission_sets = subm.autograde.map(unmapped(config), submission_sets)

            ## Wait for manual grading
            submission_sets = subm.check_manual_grading.map(unmapped(config), submission_sets)

            ## Collect grading notifications
            notifications = subm.collect_grading_notifications(submission_sets)

            ## Skip submissions for assignments with incomplete grading
            submission_sets = subm.await_completion.map(submission_sets)

            ## generate & return feedback (separate tasks for these; dont block grade upload)
            submission_sets_fdbk = subm.generate_feedback.map(unmapped(config), submission_sets)
            subm.return_feedback.map(unmapped(config), pastdue_fracs, submission_sets_fdbk)

            ## Upload grades
            submission_sets = subm.upload_grades.map(unmapped(config), submission_sets)

            ### collect posting notifications
            #notifications = subm.collect_posting_notifications(notifications, submission_sets)

            ### send notifications
            #ntfy.notify(notifications)

        flows.append(flow)
    return flows

# TODO a flow that resets an assignment; take in parameter, no interval,
# require manual task "do you really want to do this"
def build_reset_flow(_config, args):
    raise NotImplementedError

def status(args):
    print(f"Creating the {__PROJECT_NAME} client...")
    client = prefect.client.client.Client()

    # TODO this function currently just contains a bunch of (functional)
    # test code. need to turn this into a func that prints status etc

    #client.get_flow_run_info(flow_run_id)
    #client.get_task_run_info(flow_run_id, task_id, map_index = ...)
    #client.get_flow_run_state(flow_run_id)
    #client.get_task_run_state(task_run_id)

    print("Querying for flows...")
    query_args = {}
    flow_query = {
        "query": {
            "flow" : {
                "id": True,
                "settings": True,
                "run_config": True,
                "serialized_flow": True,
                "name": True,
                "archived": True,
                "project": {"name"},
                "core_version": True,
                "storage": True,
                "flow_group": {"labels"},
            }
        }
    }
    result = client.graphql(flow_query)
    flows = result.get("data", {}).get("flow", None)

    for flow in flows:
        print(FlowView.from_flow_id(flow['id']))

    flow_run_query = {
        "query": {
             "flow_run" : {
                "id": True,
                "name": True,
                "flow_id": True,
                "serialized_state": True,
                "states": {"timestamp", "serialized_state"},
                "labels": True,
                "parameters": True,
                "context": True,
                "updated": True,
                "run_config": True,
            }
        }
    }
    result = client.graphql(flow_run_query)
    flowruns = result.get("data", {}).get("flow_run", None)
    for flowrun in flowruns:
        print(FlowRunView.from_flow_run_id(flowrun['id']))

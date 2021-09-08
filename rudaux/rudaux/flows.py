import sys, os
import prefect
from prefect import Flow, unmapped, task, flatten
from prefect.engine import signals
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor, LocalDaskExecutor
from prefect.utilities.logging import get_logger
from prefect.backend import FlowView, FlowRunView
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pendulum as plm
from requests.exceptions import ConnectionError

from . import snapshot as snap
from . import assignment as subm
from . import course_api as api
from . import grader as grd


__PROJECT_NAME = "rudaux"

def register(args):
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

    print("Creating the local dask executor")
    executor = LocalDaskExecutor(num_workers = args.dask_threads)   # for DaskExecutor: cluster_kwargs = {'n_workers': 8}) #address="tcp://localhost:8786")

    flow_builders = [ (build_autoext_flows, 'autoextension', args.autoext_interval)] #,
                    #(build_snapshot_flows, 'snapshot', args.snapshot_interval)]#,#]
                    #(build_grading_flows, 'grading', args.grading_interval)]#,#]

    #flow_builders = [ (build_snapshot_flow, 'snapshot', args.snapshot_interval),
    #          (build_autoext_flow, 'autoextension', args.autoext_interval),
    #          (build_grading_flow, 'grading', args.grading_interval)]



    for build_func, flow_name, interval in flow_builders:
        print(f"Building/registering the {flow_name} flow...")
        flows = build_func(config, args)
        for flow in flows:
            flow.executor = executor
            flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                   interval = plm.duration(minutes=interval))
            flow.register(__PROJECT_NAME)

def run(args):
    print("Running the local agent...")
    agent = prefect.agent.local.agent.LocalAgent()
    agent.start()

def build_snapshot_flows(config, args):
    flows = []
    for group in config.course_groups:
        for course_id in config.course_groups[group]:
            with Flow(config.course_names[course_id]+"-snapshot") as flow:
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

def build_autoext_flows(config, args):
    flows = []
    for group in config.course_groups:
        for course_id in config.course_groups[group]:
            with Flow(config.course_names[course_id]+"-autoextension") as flow:
                # Obtain course/student/assignment/etc info from the course API
                course_info = api.get_course_info(config, course_id)
                assignments = api.get_assignments(config, course_id, list(config.assignments[group].keys()))
                students = api.get_students(config, course_id)

                # Create submissions
                submission_sets = subm.initialize_submission_sets(config, [course_info], [assignments], [students])

                # Fill in submission deadlines
                submission_sets = subm.compute_deadlines.map(submission_sets)

                # Compute override updates
                overrides = subm.get_latereg_overrides.map(unmapped(config.latereg_extension_days[group]), submission_sets)

                # Remove / create overrides
                api.update_override.map(unmapped(config), unmapped(course_id), flatten(overrides))
            flows.append(flow)
    return flows

@task(checkpoint=False)
def combine_dictionaries(dicts):
    return {k : v for d in dicts for k, v in d.items()}


# TODO this creates one flow per grading group,
# not one flow per assignment. In the future we might
# not load assignments/graders from the rudaux config but
# rather dynamically from LMS; there we dont know what
# assignments there are until runtime.
def build_grading_flows(config, args):
    flows = []
    for group in config.course_groups:
        with Flow(group+"-grading") as flow:
            # get the course ids in this group
            course_ids = config.course_groups[group]

            # Obtain course/student/assignment/etc info from the course API
            course_infos = api.get_course_info.map(unmapped(config), course_ids)
            assignment_lists = api.get_assignments.map(unmapped(config), course_ids, unmapped(list(config.assignments[group].keys())))
            student_lists = api.get_students.map(unmapped(config), course_ids)

            # Create submissions
            submission_sets = subm.initialize_submission_sets(unmapped(config), course_infos, assignment_lists, student_lists)

            # Fill in submission deadlines
            submission_sets = subm.compute_deadlines.map(submission_sets)

            # Create grader teams
            grader_teams = grd.build_grading_team.map(unmapped(config), assignments)

            # create grader volumes, add git repos, create folder structures, initialize nbgrader
            grader_teams = grd.initialize_volumes.map(unmapped(config), grader_teams)

            # create grader jhub accounts
            grader_teams = grd.initialize_accounts.map(unmapped(config), grader_teams)

            # create submission lists for each grading team, then flatten
            submissions = flatten(subm.build_submissions.map(unmapped(assignments), unmapped(students), unmapped(subm_info), grader_teams))
            submissions = subm.initialize_submission.map(unmapped(config), unmapped(course_info), submissions)

            # compute the fraction of submissions past due for each assignment, and then return solutions for all assignments past the threshold
            pastdue_fracs = subm.get_pastdue_fractions(config, course_info, submissions)
            subm.return_solution.map(unmapped(config), unmapped(course_info), unmapped(pastdue_fracs), submissions)

            # collect submissions
            submissions = subm.collect_submission.map(unmapped(config), submissions)

            # clean submissions
            submissions = subm.clean_submission.map(unmapped(config), submissions)

            # Autograde submissions
            submissions = subm.autograde_submission.map(unmapped(config), submissions)

            # Wait for manual grading
            submissions = subm.wait_for_manual_grading.map(unmapped(config), submissions)

            # Skip submissions for assignments with incomplete grading
            complete_assignments = subm.get_complete_assignments(config, assignments, submissions)
            submissions = subm.wait_for_completion.map(unmapped(config), unmapped(complete_assignments), submissions)

            # generate feedback
            submissions = subm.generate_feedback.map(unmapped(config), submissions)

            # return feedback
            submissions = subm.return_feedback.map(unmapped(config), unmapped(course_info), unmapped(pastdue_fracs), submissions)

            # Upload grades
            submissions = subm.upload_grade.map(unmapped(config),  submissions)
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

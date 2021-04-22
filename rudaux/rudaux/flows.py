import sys, os
import prefect
from prefect import Flow, unmapped, task, flatten
from prefect.engine import signals
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor, LocalDaskExecutor
from prefect.utilities.logging import get_logger
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pendulum as plm

from . import snapshot as snap
from . import submission as subm
from . import course_api as api
from . import grader as grd

@task
def combine_dictionaries(dicts):
    return {k : v for d in dicts for k, v in d.items()}

def run(args): 
    print("Loading the rudaux_config.py file...")
    if not os.path.exists(os.path.join(args.directory, 'rudaux_config.py')):
            sys.exit(
              f"""
              There is no rudaux_config.py in the directory {args.directory},
              and no course directory was specified on the command line. Please
              specify a directory with a valid rudaux_config.py file. 
              """
            )
    _config = Config()
    _config.merge(PyFileConfigLoader('rudaux_config.py', path=args.directory).load_config())

    project_name = "rudaux"

    print(f"Creating the {project_name} project...")
    prefect.client.client.Client().create_project(project_name)

    print("Creating the local Dask executor")
    executor = LocalDaskExecutor(num_workers = args.dask_threads)   # for DaskExecutor: cluster_kwargs = {'n_workers': 8}) #address="tcp://localhost:8786")


    #flow = build_test_flow()
    #flow.executor = executor
    #flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
    #                           interval = plm.duration(minutes=1))
    #flow.register(project_name)

    flows = [ (build_snapshot_flow, 'snapshot', args.snapshot_interval),
              (build_autoext_flow, 'autoextension', args.autoext_interval),
              (build_snapshot_flow, 'grading', args.grading_interval)]

    for build_func, flow_name, interval in flows:
        print(f"Building/registering the {flow_name} flow...")
        flow = build_func(_config, args)
        flow.executor = executor
        flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                               interval = plm.duration(minutes=interval))
        flow.register(project_name)

    print("Running the local agent...")
    agent = prefect.agent.local.agent.LocalAgent()
    agent.start()


#@task
#def get_list():
#    return [1, 2, 3, 4]
#
#@task
#def skip_some(num):
#    if num % 2 == 0:
#        raise signals.SKIP(f"skipped this one {num}")
#    return num
#
#@task
#def mergeli(nums):
#    logger = prefect.context.get("logger")
#    logger.info(f"this is nums: {nums}")
#    return nums[0]
#
#def build_test_flow():
#    with Flow("test") as flow:
#        li = get_list()
#        li2 = skip_some.map(li)
#        li3 = mergeli(li2)
#    return flow


def build_snapshot_flow(_config, args):
    with Flow(_config.course_name+"-snapshot") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = snap.validate_config(config)

        # Obtain course/student/assignment/etc info from the course API 
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
 
        # extract the total list of snapshots to take from assignment data
        snaps = snap.extract_snapshots(config, assignments)

        # obtain the list of existing snapshots
        existing_snaps = snap.get_existing_snapshot_names(config)
 
        # take new snapshots 
        snap.take_snapshot.map(unmapped(config), unmapped(course_info), snaps, unmapped(existing_snaps))

    return flow

# should run at the same or faster interval as the snapshot flow
def build_autoext_flow(_config, args):
    with Flow(_config.course_name+"-autoextension") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = subm.validate_config(config)

        # Obtain course/student/assignment/etc info from the course API 
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        subm_info = combine_dictionaries(api.get_submissions.map(unmapped(config), assignments))

        # Create submissions
        submissions = subm.build_submissions(assignments, students, subm_info)
        submissions = subm.initialize_submission.map(unmapped(config), unmapped(course_info), submissions)
        
        # get override updates to make
        override_updates = subm.get_latereg_override.map(unmapped(config), submissions)

        # Remove / create extensions 
        api.update_overrides.map(unmapped(config), override_updates)
         
    return flow
        
def build_grading_flow(_config, args):
    with Flow(_config.course_name+"-grading") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = grader.validate_config(config)

        # Obtain course/student/assignment/etc info from the course API 
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        subm_info = combine_dictionaries(api.get_submissions.map(unmapped(config), assignments))

        # ideally we would have individual graders, not grader teams here
        # but Prefect (Apr 2021) doesn't allow product maps yet; so in order to preserve
        # proper cascading of skips/failures/successes, we'll use this design for now
        # If Prefect implements product maps, we can probably parallelize more across individual graders

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


    return flow
 
# TODO a flow that resets an assignment; take in parameter, no interval, require manual task "do you really want to do this"
def build_reset_flow(_config, args):
    raise NotImplementedError



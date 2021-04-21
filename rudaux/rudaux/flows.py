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

        # TODO create a nested list of "grading teams" by assignment
        # some teams will fail, some will succeed
        # then do flatten(build_submissions.map(teams, assignments, students, subm_info))
        # therefore any failed or skipped team won't generate submissions
        # and in build_subms any special due dates will be skipped

        # Create submissions
        submissions = subm.build_submissions(assignments, students, subm_info)
        submissions = subm.initialize_submission.map(unmapped(config), unmapped(course_info), submissions)

        # Create graders
        graders = grd.build_graders(config, assignments)
        graders = grd.initialize_grader.map(unmapped(config), unmapped(course_info), graders)

        # create grader volume, add git repo, create folder structure, initialize nbgrader
        graders = grd.initialize_volume.map(unmapped(config), graders)

        # create grader jhub account
        graders = grd.initialize_account.map(unmapped(config), graders)

        # TODO
        # we want to propagate skips / failures from graders and submissions to grading_tasks (= combination of grader + subm)
        # ideally we'd do something like 
        #     grading_tasks = grd.assign_grading_tasks.product_map(unmapped(config), graders, submissions)
        # to iterate over all pairs of grader x submission
        # but Prefect currently (Apr 2021) doesn't allow "product maps" of two lists of tasks
        # all the options for mapping / flattening don't properly propagate skip/failure/success here
        # so in the below, we give "submissions" the jobs of:
        # 1. collecting a list of possible graders from the config
        # 2. verifying that all the grader folders are set up properly (normally we would just rely on fail / skip state from the graders list,
        #    but per earlie we can't do that right now)
        # 3. assigning themselves to a grader
        # 4. doing all the other tasks (collecting, cleaning, autograding, feedback, returning solns, etc)

        
        

 
        # combine graders and submissions to create grading tasks
        grading_tasks = flatten(grd.assign_grading_tasks.map(unmapped(config), graders, unmapped(submissions)))

        # collect submissions
        grading_tasks = grd.collect_submission.map(unmapped(config), grading_tasks)

        # clean submissions
        grading_tasks = grd.clean_submission.map(unmapped(config), grading_tasks)

        # Return solutions  
        returnables = grd.get_returnable_solutions(config, course_info, grading_tasks)
        grd.return_solution.map(unmapped(config), returnables)

        #--------------------------#
        #   Autograde submissions  #
        #--------------------------#

        #----------------------------#
        #   Wait for manual grading  #
        #----------------------------#

        #------------------#
        #   Upload grades  #
        #------------------#

        #---------------------------------#
        #   Generate and return feedback  #
        #---------------------------------#

    return flow
 

# TODO a flow that resets an assignment; take in parameter, no interval, require manual task "do you really want to do this"
def build_reset_flow(_config, args):
    with Flow(_config.course_name+"-reset") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = snap.validate_config(config)

        # Obtain course/student/assignment/etc info from the course API 
        assignments = api.get_assignments(config)
 
        # extract the total list of snapshots to take from assignment data
        snaps = snap.extract_snapshots(config, assignments)

        # obtain the list of existing snapshots
        existing_snaps = snap.get_existing_snapshot_names(config)
 
        # take new snapshots 
        snap.take_snapshot.map(unmapped(config), snaps, unmapped(existing_snaps))

    return flow



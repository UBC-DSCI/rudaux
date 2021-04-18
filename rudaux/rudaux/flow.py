import sys, os
import prefect
from prefect import Flow, unmapped
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor, LocalDaskExecutor
from prefect.utilities.logging import get_logger
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pendulum as plm

from .course_api import canvas as api
from .snapshot import zfs_over_ssh as snap

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

    project_name = "Rudaux"

    print(f"Creating the {project_name} project...")
    prefect.client.client.Client().create_project(project_name)

    print("Creating Dask executor")
    executor = LocalDaskExecutor(num_workers = 8)   # for DaskExecutor: cluster_kwargs = {'n_workers': 8}) #address="tcp://localhost:8786")

    print("Building/registering the snapshot flow...")
    snap_flow = build_snapshot_flow(_config)
    snap_flow.executor = executor
    snap_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                interval = plm.duration(minutes=args.snapshot_interval))
    snap_flow.register(project_name)

    print("Building/registering the late registration auto-extension flow...")
    autoext_flow = build_autoextension_flow(_config)
    autoext_flow.executor = executor
    autoext_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                interval = plm.duration(minutes=args.autoext_interval))
    autoext_flow.register(project_name)

    print("Building/registering the grading flow...")
    grading_flow = build_grading_flow(_config)
    grading_flow.executor = executor
    grading_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                interval = plm.duration(minutes=args.grading_interval))
    grading_flow.register(project_name)

    print("Running the local agent...")
    agent = prefect.agent.local.agent.LocalAgent()
    agent.start()
    
def build_snapshot_flow(_config):
    with Flow("rudaux-snapshot") as flow:
        #################################################################
        # Obtain course/student/assignment/etc info from the course API #
        #################################################################

        # validate the config file for API access
        config = api.validate_config(_config)

        # obtain course info, students, assignments, etc
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        tas = api.get_tas(config)
        instructors = api.get_instructors(config)

        ################################
        # Obtain the list of snapshots #
        ################################
 
        # validate the config file for snapshots
        config = snap.validate_config(_config)
        
        # extract the total list of snapshots to take from assignment data
        snaps = extract_snapshots(assignments)

        ## obtain the list of existing snapshots
        #existing_snaps = get_existing_snapshots(config)

        ## take snapshots (map over snaps)
        #take_snapshot.map(unmapped(config), snaps, unmapped(existing_snaps))
    return flow
        
def build_autoext_flow(_config):
    with Flow("rudaux-autoextension") as flow:
        #################################################################
        # Obtain course/student/assignment/etc info from the course API #
        #################################################################

        # validate the config file for API access
        config = api.validate_config(_config)

        # obtain course info, students, assignments, etc
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        tas = api.get_tas(config)
        instructors = api.get_instructors(config)

        ################################
        # Obtain the list of snapshots #
        ################################
 
        # validate the config file for snapshots
        config = snap.validate_config(_config)
        
        # extract the total list of snapshots to take from assignment data
        snaps = extract_snapshots(assignments)

    return flow
        
def build_grading_flow(_config):
    with Flow("rudaux-grading") as flow:
        #################################################################
        # Obtain course/student/assignment/etc info from the course API #
        #################################################################

        # validate the config file for API access
        config = api.validate_config(_config)

        # obtain course info, students, assignments, etc
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        tas = api.get_tas(config)
        instructors = api.get_instructors(config)

        ################################
        # Obtain the list of snapshots #
        ################################
 
        # validate the config file for snapshots
        config = snap.validate_config(_config)
        
        # extract the total list of snapshots to take from assignment data
        snaps = extract_snapshots(assignments)

    return flow
        


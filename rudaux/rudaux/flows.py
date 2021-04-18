import sys, os
import prefect
from prefect import Flow, unmapped, task, flatten
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor, LocalDaskExecutor
from prefect.utilities.logging import get_logger
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pendulum as plm
import importlib

from .util import build_submission_triplet, reduce_override_pairs

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

    print("Creating Dask executor")
    executor = LocalDaskExecutor(num_workers = 8)   # for DaskExecutor: cluster_kwargs = {'n_workers': 8}) #address="tcp://localhost:8786")

    print("Building/registering the snapshot flow...")
    snap_flow = build_snapshot_flow(_config, args)
    snap_flow.executor = executor
    snap_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                interval = plm.duration(minutes=args.snapshot_interval))
    snap_flow.register(project_name)

    print("Building/registering the autoextension flow...")
    autoext_flow = build_autoext_flow(_config, args)
    autoext_flow.executor = executor
    autoext_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                   interval = plm.duration(minutes=args.autoext_interval))
    autoext_flow.register(project_name)


    print("Building/registering the grading flow...")
    grading_flow = build_grading_flow(_config, args)
    grading_flow.executor = executor
    grading_flow.schedule = IntervalSchedule(start_date = plm.now('UTC').add(seconds=1),
                                interval = plm.duration(minutes=args.grading_interval))
    grading_flow.register(project_name)

    print("Running the local agent...")
    agent = prefect.agent.local.agent.LocalAgent()
    agent.start()
    
def build_snapshot_flow(_config, args):
    print("Importing course API, snapshot libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    snap = importlib.import_module(".snapshot."+args.snapshot_module, "rudaux")

    with Flow("snapshot") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)

        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#
        assignments = api.get_assignments(config)

        #------------------------------#
        # Obtain the list of snapshots #
        #------------------------------#
 
        # validate the config file for snapshots
        config = snap.validate_config(_config)
        
        # extract the total list of snapshots to take from assignment data
        snaps = snap.extract_snapshots(config, assignments)

        ## obtain the list of existing snapshots
        # TODO uncomment + test 
        #existing_snaps = snap.get_existing_snapshots(config)

        ## take snapshots (map over snaps)
        # TODO uncomment + test 
        #snap.take_snapshot.map(unmapped(config), snaps, unmapped(existing_snaps))
    return flow

def build_autoext_flow(_config, args):
    print("Importing course API, autoextension libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    autoext = importlib.import_module(".auto_extension."+args.autoext_module, "rudaux")
    with Flow("autoextension") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = autoext.validate_config(_config)

        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)

        #----------------------------#
        # Create submission triplets #
        #----------------------------#
        subm_pairs = build_assignment_student_pairs(assignments, students) 

        #----------------------------#
        # Remove / create extensions #
        #----------------------------#
        override_create_remove_pairs = autoext.manage_extensions.map(unmapped(config), unmapped(course_info), subm_pairs)
        overrides_to_create, overrides_to_remove = reduce_override_pairs(override_create_remove_pairs)
        # TODO uncomment these + test
        #api.remove_override.map(unmapped(config), overrides_to_remove)
        #api.create_override.map(unmapped(config), overrides_to_create)
         
    return flow
        

def build_grading_flow(_config, args):
    print("Importing course API libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    with Flow("autoextension") as flow:
        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#

        # validate the config file for API access
        config = api.validate_config(_config)

        # TODO only obtain resources actually required here
        # obtain course info, students, assignments, etc
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        submissions = flatten(api.get_submissions.map(unmapped(config), assignments))

        #----------------------------#
        # Create submission triplets #
        #----------------------------#
        subm_triplets = build_submission_triplet.map(unmapped(assignments), unmapped(students), submissions) 

        #----------------------------#
        # Remove / create extensions #
        #----------------------------#
        config = autoext.validate_config(_config)
        override_create_remove_pairs = autoext.manage_extensions.map(unmapped(config), unmapped(course_info), subm_triplets)
        overrides_to_create, overrides_to_remove = reduce_override_pairs(override_create_remove_pairs)
        # TODO uncomment these + test
        #api.remove_override.map(unmapped(config), overrides_to_remove)
        #api.create_override.map(unmapped(config), overrides_to_create)
         
    return flow
 

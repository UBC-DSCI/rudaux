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

from .util import build_submission_triplet, build_assignment_student_pairs, reduce_override_pairs, combine_dictionaries

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

def build_snapshot_flow(_config, args):

    print("Importing course API, snapshot libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    snap = importlib.import_module(".snapshot."+args.snapshot_module, "rudaux")

    print("Constructing the flow")
    with Flow(_config.course_name+"-snapshot") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = snap.validate_config(config)

        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#
        assignments = api.get_assignments(config)

        #------------------------------#
        #  Obtain lists of snapshots   #
        #------------------------------#
 
        # extract the total list of snapshots to take from assignment data
        snaps = snap.extract_snapshots(config, assignments)

        # obtain the list of existing snapshots
        # TODO uncomment + test 
        #existing_snaps = snap.get_existing_snapshots(config)
 
        #--------------------#
        # Take new snapshots #
        #--------------------#
        # TODO uncomment + test 
        #snap.take_snapshot.map(unmapped(config), snaps, unmapped(existing_snaps))
    return flow

# should run at the same or faster interval as the snapshot flow
# TODO merge this with the snapshot flow?
# maybe not -- if one fails don't want to stop the other...
def build_autoext_flow(_config, args):

    print("Importing course API, autoextension libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    autoext = importlib.import_module(".auto_extension."+args.autoext_module, "rudaux")

    print("Constructing the flow")
    with Flow(_config.course_name+"-autoextension") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = autoext.validate_config(config)

        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)

        #----------------------------#
        # Create submission pairs    #
        #----------------------------#
        subm_pairs = build_assignment_student_pairs(assignments, students) 

        #----------------------------#
        # Remove / create extensions #
        #----------------------------#
        override_update_tuples = autoext.manage_extensions.map(unmapped(config), unmapped(course_info), subm_pairs)
        # TODO uncomment these + test
        #api.update_overrides.map(unmapped(config), override_update_tuples)
         
    return flow
        
def build_grading_flow(_config, args):
    print("Importing course API libraries")
    api = importlib.import_module(".course_api."+args.course_api_module, "rudaux")
    grader = importlib.import_module(".grader."+args.grader_module, "rudaux")
    
    print("Constructing the flow")
    with Flow(_config.course_name+"-grading") as flow:
        # validate the config file for API access
        config = api.validate_config(_config)
        config = grader.validate_config(config)

        #---------------------------------------------------------------#
        # Obtain course/student/assignment/etc info from the course API #
        #---------------------------------------------------------------#
        course_info = api.get_course_info(config)
        assignments = api.get_assignments(config)
        students = api.get_students(config)
        submission_info = combine_dictionaries(api.get_submissions.map(unmapped(config), assignments))

        #----------------------#
        # Initialize graders   #
        #----------------------#
        #grd_tuples = grader.get_grader_assignment_tuples(config, assignments)
        #grd_tuples = grader.initialize_grader.map(config, grd_tuples)

        #-----------------------#
        #   Assign submissions  #
        #-----------------------#

        # TODO don't use tuples here, use an actual submission object

        #subm_tuples = flatten(grader.assign_submissions.map(unmapped(config), unmapped(students), unmapped(submissions), grd_tuples))

        #------------------------#
        #   Collect submissions  #
        #------------------------#
 
        #subm_tuples = grader.collect_submission.map(unmapped(config), subm_tuples)

        #----------------------#
        #   Clean submissions  #
        #----------------------#

        #subm_tuples = grader.clean_submission.map(unmapped(config), subm_tuples)
 
        #---------------------#
        #   Return solutions  #
        #---------------------#

        # returnable_subms = grader.get_returnable_solutions(config, course_info, subm_tuples)
        # grader.return_solution.map(unmapped(config), returnable_subms)

        #-------------------------------#
        #   Handle missing submissions  #
        #-------------------------------#

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
 

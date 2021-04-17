import sys, os
from prefect import Flow
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader

from .course_api import canvas as api
#from .snapshot import zfs_over_ssh as snap

def run(args):
    print("Loading the rudaux_config.py file...")
    # load the config file
    if not os.path.exists(os.path.join(args.directory, 'rudaux_config.py')):
            sys.exit(
              f"""
              There is no rudaux_config.py in the directory {args.directory},
              and no course directory was specified on the command line. Please
              specify a directory with a valid rudaux_config.py file. 
              """
            )
    __config = Config()
    __config.merge(PyFileConfigLoader('rudaux_config.py', path=course_dir).load_config())

    print("Ensuring the prefect server and agent are running")
    # TODO

    print("Constructing the prefect flow...")
    ## register the rudaux grading flow
    #schedule = IntervalSchedule(start_date = datetime.utcnow() + timedelta(seconds=1),
    #                            interval = timedelta(minutes=interval))
    #with Flow("rudaux-grading", schedule=schedule) as flow:
    #    logger = prefect.context.get("logger")
    #    __config
    #    config = api.validate_config(_config)
    #    #subms = api.get_submissions(config, asgn)
    #    #asgns = api.get_assignments(config, typeid)
    #    #studs = api.get_students(config)
    #    #tas = api.get_tas(config)
    #    #insts = api.get_instructors(config)
    #    #grps = api.get_groups(config)
    #    cinfo = api.get_course_info(config)
    #    logger.info(str(cinfo))
    #print("Registering the flow and executing...")
    #executor = DaskExecutor(address="tcp://localhost:8786")
    #flow.register()
    #flow.run(executor=executor)


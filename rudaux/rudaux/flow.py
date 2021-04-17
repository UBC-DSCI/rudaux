import sys, os
from prefect import Flow
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor
from traitlets.config import Config
from traitlets.config.loader import PyFileConfigLoader
import pyfiglet

from .course_api import canvas as api
#from .snapshot import zfs_over_ssh as snap

def run(args):
    banner = pyfiglet.figlet_format("Rudaux")
    banner += "\n\n Visit the official documentation at https://ubc-dsci.github.io/rudaux\n\n"
    print(banner)
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
    _config = Config()
    _config.merge(PyFileConfigLoader('rudaux_config.py', path=course_dir).load_config())

    print("Constructing the prefect flow...")
    # register the rudaux grading flow
    schedule = IntervalSchedule(start_date = datetime.utcnow() + timedelta(seconds=1),
                                interval = timedelta(minutes=interval))
    with Flow("rudaux-grading", schedule=schedule) as flow:
        config = api.validate_config(_config)
        api.get_submissions(config, asgn)
        api.get_assignments(config, typeid)
        api.get_course_info(config)
        api.get_students(config)
        api.get_tas(config)
        api.get_instructors(config)
        api.get_groups(config)
        pass
    print("Registering the flow and executing...")
    executor = DaskExecutor(address="tcp://localhost:8786")
    flow.register()
    flow.run(executor=executor)

    ## register the snapshot flow
    #schedule = IntervalSchedule(start_date = datetime.utcnow() + timedelta(seconds=1),
    #                            interval = timedelta(minutes=interval))
    #with Flow("rudaux-snapshots", schedule=schedule) as flow:
    #    pass

    #executor = DaskExecutor(address="tcp://localhost:8786")
    #flow.register()
    #flow.run(executor=executor)

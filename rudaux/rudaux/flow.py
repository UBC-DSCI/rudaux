from prefect import Flow
from prefect.schedules import IntervalSchedule
from prefect.executors import DaskExecutor
from .course_api import canvas

def run(args):
    # register the rudaux grading flow
    schedule = IntervalSchedule(start_date = datetime.utcnow() + timedelta(seconds=1),
                                interval = timedelta(minutes=interval))
    with Flow("rudaux-grading", schedule=schedule) as flow:
        pass
    executor = DaskExecutor(address="tcp://localhost:8786")
    flow.register()
    flow.run(executor=executor)

    # register the snapshot flow
    schedule = IntervalSchedule(start_date = datetime.utcnow() + timedelta(seconds=1),
                                interval = timedelta(minutes=interval))
    with Flow("rudaux-snapshots", schedule=schedule) as flow:
        pass

    executor = DaskExecutor(address="tcp://localhost:8786")
    flow.register()
    flow.run(executor=executor)

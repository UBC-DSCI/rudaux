import sys, os
import prefect
from prefect.deployments import DeploymentSpec
from prefect.orion.schemas.schedules import CronSchedule
from prefect import task, flow
from prefect.flow_runners import SubprocessFlowRunner
from prefect.blocks.storage import TempStorageBlock
from prefect.client import get_client
from prefect.cli.agent import start
from .models.settings import Settings

#from traitlets.config import Config
#from traitlets.config.loader import PyFileConfigLoader
#import pendulum as plm
#from requests.exceptions import ConnectionError
#from subprocess import check_output, STDOUT, CalledProcessError
#import time

#import threading
#
#from . import snapshot as snap
#from . import submission as subm
#from . import course_api as api
#from . import grader as grd
#from . import notification as ntfy

@task
def create_list():
    return [1, 2, 3, 4, 5]

@task
def multiply(li):
    return [a*3 for a in li]

@task 
def sum_list(li):
    return sum(li)

@flow(name = "test-flow-1")
def test_flow_1():
    li = create_list()
    li2 = multiply(li)
    s = sum_list(li)
    return s
    
@flow(name = "test-flow-2")
def test_flow_2():
    li = create_list()
    s = sum_list(li)
    return s

async def test(args):
    print("Test flow")

    ds1 = DeploymentSpec(
        name="deployment-1",
        flow = test_flow_1,
        flow_storage = TempStorageBlock(),
        schedule=CronSchedule(cron="* * * * *"),
        flow_runner = SubprocessFlowRunner(),
        #flow_location="/path/to/flow.py",
        #timezone = "America/Vancouver"
    )

    ds2 = DeploymentSpec(
        name="deployment-2",
        flow = test_flow_2,
        flow_storage = TempStorageBlock(),
        schedule=CronSchedule(cron="* * * * *"),
        flow_runner = SubprocessFlowRunner(),
        #flow_location="/path/to/flow.py",
        #timezone = "America/Vancouver"
    )

    dpl1 = await ds1.create_deployment()
    dpl2 = await ds2.create_deployment()

    try:
        async with get_client() as client:
            await client.create_work_queue(
                  name = "rudaux_queue",
                  deployment_ids = [dpl1, dpl2]
            )
    except:
        pass

    await start("rudaux_queue")

async def run(args):
    print(f"Loading the rudaux configuration file {args.config_path}...")
    if not os.path.exists(args.config_path):
            sys.exit(
              f"""
              There is no configuration file at {args.config_path},
              and no other file was specified on the command line. Please
              specify a valid configuration file path.
              """
            )

    settings = Settings.parse_file(args.config_path)


@flow
def autoext_flow(settings, args.config_path):
    # Create an LMS API connection
    lms = LMSAPI(api_info)

async def list_course_info(args):
    pass

async def status(args):
    pass
 
#def run(args):
#    print("Creating/running flows in local threads")
#    flows, config = _collect_flows(args)
#    threads = []
#    for flow in flows:
#        threads.append(threading.Thread(target=flow[0], name=flow[1], args=(config,)))
#
#    for thread in threads:
#        thread.start()
#
#    for thread in threads:
#        thread.join()
#    return
#
#def _collect_flows(args):
#    print("Loading the rudaux_config.py file...")
#    if not os.path.exists(os.path.join(args.directory, 'rudaux_config.py')):
#            sys.exit(
#              f"""
#              There is no rudaux_config.py in the directory {args.directory},
#              and no course directory was specified on the command line. Please
#              specify a directory with a valid rudaux_config.py file.
#              """
#            )
#    config = Config()
#    config.merge(PyFileConfigLoader('rudaux_config.py', path=args.directory).load_config())
#
#    # validate the config file
#    print("Validating the config file...")
#    api.validate_config(config)
#    snap.validate_config(config)
#    subm.validate_config(config)
#    grd.validate_config(config)
#    ntfy.validate_config(config)
#
#    flows = []
#    if args.snap or args.all_flows:
#        flows.append((snapshot_flow, 'snapshot'))
#    if args.autoext or args.all_flows:
#        flows.append((autoext_flow, 'autoextension'))
#    if args.grade or args.all_flows:
#        flows.append((grading_flow, 'grading'))
#
#    return flows, config
#
#def fail_handler_gen(config):
#    def fail_handler(flow, state, ref_task_states):
#        if state.is_failed():
#            sm = ntfy.SendMail(config)
#            sm.notify(config.instructor_user, f"Hi Instructor, \r\n Flow failed!\r\n Message:\r\n{state.message}")
#    return fail_handler
#
#@flow
#def autoext_flow(api_info):
#    # Create an LMS API connection
#    lms = LMSAPI(api_info)
#
#    # Get raw student / assignment info from LMS
#    _students, _assignments = get_students_assignments(lms)
#
#    # map over each list, creating and validating student / assignment object lists (validation)
#    students = validate_student.map(_students)
#    assignments = validate_assignment.map(_assignments)
#
#    # pairwise map student/assignment lists to compute extensions / updates (consider students who need to be removed from multiple-extension lists)
#    override_updates = compute_override_update.product_map(students, assignments)
#
#    # reduce to set of updates to apply 
#    override_updates = reduce_override_updates(override_updates)
#
#    # apply each update
#
#
#    # Obtain assignments/students/submissions from the course API
#    assignments = lms.get_assignments()
#    students = lms.get_students()
#
#    # Compute automatic extensions
#    extensions = lms.get_automatic_extensions(assignments, students, interval)
#
#    # Update LMS with automatic extensions
#    lms.update_overrides(extensions)
#
#    # end func
#
#def build_autoext_flows(config):
#    """
#    Build the flow for the auto-extension of assignments for students
#    who register late.
#
#    Params
#    ------
#    config: traitlets.config.loader.Config
#        a dictionary-like object containing the configurations
#        from rudaux_config.py
#    """
#    flows = []
#    for group in config.course_groups:
#        for course_id in config.course_groups[group]:
#            with Flow(config.course_names[course_id] + "-autoext",
#                      terminal_state_handler=fail_handler_gen(config)) as flow:
#
#                assignment_names = list(config.assignments[group].keys())
#
#                # Obtain course/student/assignment/etc info from the course API
#                course_info = api.get_course_info(config, course_id)
#                assignments = api.get_assignments(config, course_id, assignment_names)
#                students = api.get_students(config, course_id)
#                submission_info = combine_dictionaries(api.get_submissions.map(unmapped(config), unmapped(course_id), assignments))
#
#                # Create submissions
#                submission_sets = subm.initialize_submission_sets(config, [course_info], [assignments], [students], [submission_info])
#
#                # Fill in submission deadlines
#                submission_sets = subm.build_submission_set.map(unmapped(config), submission_sets)
#
#                # Compute override updates
#                overrides = subm.get_latereg_overrides.map(unmapped(config.latereg_extension_days[group]), submission_sets, unmapped(config))
#
#                # TODO: we would ideally do flatten(overrides) and then
#                # api.update_override.map(unmapped(config), unmapped(course_id), flatten(overrides))
#                # but that will cause prefect to fail. see https://github.com/PrefectHQ/prefect/issues/4084
#                # so instead we will code a temporary hack for update_override.
#                api.update_override_flatten.map(unmapped(config), unmapped(course_id), overrides)
#
#            flows.append(flow)
#    return flows
#
#
#
#
#def snapshot_flow(config):
#    interval = config.snapshot_interval
#    while True:
#        for group in config.course_groups:
#            # Create an LMS API connection
#            lms = LMSAPI(group, config)
#
#            # Create a Student API connection
#            stu = StudentAPI(group, config)
#
#            # Obtain assignments from the course API
#            assignments = lms.get_assignments()
#
#            # obtain the list of existing snapshots
#            existing_snaps = stu.get_snapshots()
#
#            # compute snapshots to take
#            snaps_to_take = stu.compute_snaps_to_take(assignments, existing_snaps)
#
#            # take new snapshots
#            stu.take_snapshots(snaps_to_take)
#
#        # sleep until the next run time
#        print(f"Snapshot waiting {interval} minutes for next run...")
#        time.sleep(interval*60)
#    # end func
#
## this creates one flow per grading group,
## not one flow per assignment. In the future we might
## not load assignments/graders from the rudaux config but
## rather dynamically from LMS; there we dont know what
## assignments there are until runtime. So doing it by group is the
## right strategy.
#def grading_flow(config):
#    try:
#        check_output(['sudo', '-n', 'true'])
#    except CalledProcessError as e:
#        assert False, f"You must have sudo permissions to run the flow. Command: {e.cmd}. returncode: {e.returncode}. output {e.output}. stdout {e.stdout}. stderr {e.stderr}"
#    hour = config.grade_hour
#    minute = config.grade_minute
#    while True:
#        # wait for next grading run
#        t = plm.now().in_tz(config.grading_timezone)
#        print(f"Time now: {t}")
#        tgrd = plm.now().at(hour = hour, minute = minute)
#        if t > tgrd:
#            tgrd = tgrd.add(days=1)
#        print(f"Next grading flow run: {tgrd}")
#        print(f"Grading waiting {(tgrd-t).total_hours()} hours for run...")
#        time.sleep((tgrd-t).total_seconds())
#
#        # start grading run
#        for group in config.course_groups:
#            # get the course names in this group
#            course_names = config.course_groups[group]
#            # create connections to APIs
#            lsapis = {}
#            for course_name in course_names:
#                lsapis[course_name]['lms'] = LMSAPI(course_name, config)
#                lsapis[course_name]['stu'] = StudentAPI(course_name, config)
#            # Create a Grader API connection
#            grd = GraderAPI(group, config)
#
#
#            # Obtain course/student/assignment/etc info from the course API
#            course_infos = api.get_course_info.map(unmapped(config), course_ids)
#            assignment_lists = api.get_assignments.map(unmapped(config), course_ids, unmapped(assignment_names))
#            student_lists = api.get_students.map(unmapped(config), course_ids)
#            submission_infos = []
#            for i in range(len(course_ids)):
#                submission_infos.append(combine_dictionaries(api.get_submissions.map(unmapped(config), unmapped(course_ids[i]), assignment_lists[i])))
#
#            # Create submissions
#            submission_sets = subm.initialize_submission_sets(unmapped(config), course_infos, assignment_lists, student_lists, submission_infos)
#
#            # Fill in submission details
#            submission_sets = subm.build_submission_set.map(unmapped(config), submission_sets)
#
#            # Create grader teams
#            grader_teams = grd.build_grading_team.map(unmapped(config), unmapped(group), submission_sets)
#
#            # create grader volumes, add git repos, create folder structures, initialize nbgrader
#            grader_teams = grd.initialize_volumes.map(unmapped(config), grader_teams)
#
#            # create grader jhub accounts
#            grader_teams = grd.initialize_accounts.map(unmapped(config), grader_teams)
#
#            # assign graders
#            submission_sets = subm.assign_graders.map(unmapped(config), submission_sets, grader_teams)
#
#            # compute the fraction of submissions past due for each assignment,
#            # and then return solutions for all assignments past the threshold
#            pastdue_fracs = subm.get_pastdue_fraction.map(submission_sets)
#            subm.return_solutions.map(unmapped(config), pastdue_fracs, submission_sets)
#
#            ## collect submissions
#            submission_sets = subm.collect_submissions.map(unmapped(config), submission_sets)
#
#            ## clean submissions
#            submission_sets = subm.clean_submissions.map(submission_sets)
#
#            ## Autograde submissions
#            submission_sets = subm.autograde.map(unmapped(config), submission_sets)
#
#            ## Wait for manual grading
#            submission_sets = subm.check_manual_grading.map(unmapped(config), submission_sets)
#
#            ## Collect grading notifications
#            grading_notifications = subm.collect_grading_notifications.map(submission_sets)
#
#            ## Skip assignments with incomplete manual grading
#            submission_sets = subm.await_completion.map(submission_sets)
#
#            ## generate & return feedback
#            submission_sets = subm.generate_feedback.map(unmapped(config), submission_sets)
#            subm.return_feedback.map(unmapped(config), pastdue_fracs, submission_sets)
#
#            ## Upload grades
#            submission_sets = subm.upload_grades.map(unmapped(config), submission_sets)
#
#            ## collect posting notifications
#            posting_notifications = subm.collect_posting_notifications.map(submission_sets)
#
#            ## send notifications
#            grading_notifications = filter_skip(grading_notifications)
#            posting_notifications = filter_skip(posting_notifications)
#            ntfy.notify(config, grading_notifications, posting_notifications)
#        # end while
#    # end func
#
## TODO a flow that resets an assignment; take in parameter, no interval,
## require manual task "do you really want to do this"
#def build_reset_flow(_config, args):
#    raise NotImplementedError
#
#def status(args):
#    print(f"Creating the {__PROJECT_NAME} client...")
#    client = prefect.client.client.Client()
#
#    # TODO this function currently just contains a bunch of (functional)
#    # test code. need to turn this into a func that prints status etc
#
#    #client.get_flow_run_info(flow_run_id)
#    #client.get_task_run_info(flow_run_id, task_id, map_index = ...)
#    #client.get_flow_run_state(flow_run_id)
#    #client.get_task_run_state(task_run_id)
#
#    print("Querying for flows...")
#    query_args = {}
#    flow_query = {
#        "query": {
#            "flow" : {
#                "id": True,
#                "settings": True,
#                "run_config": True,
#                "serialized_flow": True,
#                "name": True,
#                "archived": True,
#                "project": {"name"},
#                "core_version": True,
#                "storage": True,
#                "flow_group": {"labels"},
#            }
#        }
#    }
#    result = client.graphql(flow_query)
#    flows = result.get("data", {}).get("flow", None)
#
#    for flow in flows:
#        print(FlowView.from_flow_id(flow['id']))
#
#    flow_run_query = {
#        "query": {
#             "flow_run" : {
#                "id": True,
#                "name": True,
#                "flow_id": True,
#                "serialized_state": True,
#                "states": {"timestamp", "serialized_state"},
#                "labels": True,
#                "parameters": True,
#                "context": True,
#                "updated": True,
#                "run_config": True,
#            }
#        }
#    }
#    result = client.graphql(flow_run_query)
#    flowruns = result.get("data", {}).get("flow_run", None)
#    for flowrun in flowruns:
#        print(FlowRunView.from_flow_run_id(flowrun['id']))
#
#def print_list(args):
#    course = rudaux.Course(args.directory)
#    printouts = {'students' : 'Students', 'groups' : 'Groups', 'instructors' : 'Instructors', 'tas' : 'Teaching Assistants', 'assignments' : 'Assignments'}
#    none_selected = not any([vars(args)[po] for po in printouts])
#    for po in printouts:
#        if vars(args)[po] or none_selected:
#            title = printouts[po]
#            if len(course.__dict__[po]) > 0:
#                tbl = [type(course.__dict__[po][0]).table_headings()]
#                for obj in course.__dict__[po]:
#                    tbl.append(obj.table_items())
#            else:
#                tbl = []
#            print(ttbl.AsciiTable(tbl, title).table)
#
#def list_course_info(args):
#    print("Loading the rudaux_config.py file...")
#    if not os.path.exists(os.path.join(args.directory, 'rudaux_config.py')):
#            sys.exit(
#              f"""
#              There is no rudaux_config.py in the directory {args.directory},
#              and no course directory was specified on the command line. Please
#              specify a directory with a valid rudaux_config.py file.
#              """
#            )
#    config = Config()
#    config.merge(PyFileConfigLoader('rudaux_config.py', path=args.directory).load_config())
#
#    # validate the config file
#    print("Validating the config file...")
#    api.validate_config(config)
#    asgns = []
#    studs = []
#    tas = []
#    insts = []
#    for group in config.course_groups:
#        for course_id in config.course_groups[group]:
#            course_name = config.course_names[course_id]
#            asgns.extend([(course_name, a) for a in api._canvas_get(config, course_id, 'assignments')])
#            studs.extend([(course_name, s) for s in api._canvas_get_people_by_type(config, course_id, 'StudentEnrollment')])
#            tas.extend([(course_name, s) for s in api._canvas_get_people_by_type(config, course_id, 'TaEnrollment')])
#            insts.extend([(course_name, s) for s in api._canvas_get_people_by_type(config, course_id, 'TeacherEnrollment')])
#    print()
#    print('Assignments')
#    print()
#    print('\n'.join([f"{c[0] : <16}{c[1]['name'] : <32}{c[1]['id'] : <16}" for c in asgns]))
#
#    print()
#    print('Students')
#    print()
#    print('\n'.join([f"{c[0] : <16}{c[1]['name'] : <32}{c[1]['id'] : <16}{str(c[1]['reg_date'].in_timezone(config.notify_timezone)) : <32}{c[1]['status'] : <16}" for c in studs]))
#
#    print()
#    print('Teaching Assistants')
#    print()
#    print('\n'.join([f"{c[0] : <16}{c[1]['name'] : <32}{c[1]['id'] : <16}{str(c[1]['reg_date'].in_timezone(config.notify_timezone)) : <32}{c[1]['status'] : <16}" for c in tas]))
#
#    print()
#    print('Instructors')
#    print()
#    print('\n'.join([f"{c[0] : <16}{c[1]['name'] : <32}{c[1]['id'] : <16}{str(c[1]['reg_date'].in_timezone(config.notify_timezone)) : <32}{c[1]['status'] : <16}" for c in insts]))

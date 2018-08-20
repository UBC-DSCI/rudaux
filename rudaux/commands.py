import sys
from subprocess import CalledProcessError
from rudaux import Course, Assignment


def initialize_course(args):
  """Fully Initialize a course. This involves:
  0. Reading your configuration file and ensuring all parameters are valid.
  1. Identifying the tool name used for your JupyterHub installation in Canvas.
  2. Pulling your student list from Canvas.  
  3. Syncing Canvas with nbgrader (students & assignments).
  4. Assigning all of the assignments listed in your config file.
  5. Creating the assignments listed in your config file in Canvas.
  6. Schedule automated grading of your assignments.

  :param args: Arguments passed in from the command line parser.
  """

  course = Course(course_dir=args.directory, auto=args.auto)

  # course.schedule_grading()

  course                                   \
    .get_external_tool_id()                \
    .get_students_from_canvas()            \
    .sync_nbgrader()                       \
    .assign(overwrite=args.overwrite)      \
    .create_canvas_assignments()           \
    .schedule_grading()


def grade(args):
  """Grade an assignment.
  1. If we are using a ZFS storage system, snapshot with ZFS.
  2. ? Copy to a temporary directory
  3. Collect assignments with nbgrader
  4. Grade assignments with nbgrader
  5. If no manual input, generate forms
  6. If no manual input, return forms and submit grades
  
  :param args: Arguments passed in from the command line parser.
  """

  course = Course(course_dir=args.directory, auto=args.auto)

  course = course               \
    .get_external_tool_id()     \
    .get_students_from_canvas() \
    .sync_nbgrader()

  # find assignment in config assignment list
  assignment = list(
    filter(lambda assn: assn.name == args.assignment_name, course.assignments)
  )

  if len(assignment) <= 0:
    sys.exit(f"No assignment named \"{args.assignment_name}\" found")
  else:
    # Take the first result.
    assignment = assignment[0]
    # But notify if more than one was found
    # Though this should never happen--assignment names must be unique.
    if len(assignment) > 1:
      print(
        f"Multiple assignments named \"{args.assignment_name}\" were found. Grading the first one!"
      )

  # collect and grade the assignment
  assignment = assignment \
    .collect()            \
    .grade()

  # and if no manual feedback is required, generate feedback reports
  # and submit grades
  if not args.manual:
    assignment    \
      .feedback() \
      .submit()


def submit(args):
  """Generate feedback for and submit an assignment.
  
  :param args: Arguments passed in from the command line parser.
  """

  # no auto arg needed, this would only ever be run after manual feedback, and
  # thus not as a cron job
  course = Course(course_dir=args.directory)

  course = course               \
    .get_external_tool_id()     \
    .get_students_from_canvas() \
    .sync_nbgrader()

  # find assignment in config assignment list
  assignment = list(
    filter(lambda assn: assn.name == args.assignment_name, course.assignments)
  )

  if len(assignment) <= 0:
    sys.exit(f"No assignment named \"{args.assignment_name}\" found")
  else:
    # Take the first result
    assignment = assignment[0]
    # If we run into this situation, there's probably a lot of other weird things going wrong already.
    if len(assignment) > 1:
      print(
        f"Multiple assignments named \"{args.assignment_name}\" were found. Grading the first one!"
      )

    assignment    \
      .feedback() \
      .submit()
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

  course = Course(args.directory)

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

  this_course = Course(args.directory)

  this_course = this_course                \
    .get_external_tool_id()                \
    .get_students_from_canvas()            \
    .sync_nbgrader()

  # Subclass assignment for this course:
  # class CourseAssignment(Assignment):
  #   course = this_course

  # find assignment in config assignment list
  assignment = list(
    filter(lambda assn: assn.name == args.assignment_name, this_course.assignments)
  )

  if len(assignment) <= 0:
    sys.exit(f"No assignment named \"{args.assignment_name}\" found")
  else:
    assignment = assignment[0]

  # assignment = CourseAssignment(
  #   name=args.assignment_name,
  #   manual=args.manual,
  #   course=None,
  #   status='unassigned',
  # )

  assignment = assignment   \
    .grade()                \
    .collect()

  if not args.manual:
    assignment = assignment \
      .feedback()           \
      .submit()
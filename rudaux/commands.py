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

  course = Course()

  course                         \
    .get_external_tool_id()      \
    .get_students_from_canvas()  \
    .sync_nbgrader()             \
    .assign_all(args.overwrite)  \
    .create_canvas_assignments() \
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

  this_course = Course()

  # Subclass assignment for this course:
  class CourseAssignment(Assignment):
    course = this_course

  assignment = CourseAssignment(
    name=args.assignment_name,
    manual=args.manual,
    course=None,
    status='unassigned',
  )

  if this_course.zfs:
    try:
      assignment.snapshot_zfs()
    except CalledProcessError as e:
      print(e)

  assignment.collect()
  assignment.grade()
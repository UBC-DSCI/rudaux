import sys
from rudaux import Course


def initialize_course(args):
  """Fully Initialize a course. 
  :param args: Arguments passed in from the command line parser.

  0. Read your course configuration file and ensure all parameters are valid.
  1. Identify the tool name used for your JupyterHub installation in Canvas.
  2. Pull your student list from Canvas.  
  3. Sync students & assignments between Canvas and nbgrader.
  4. Assign all of the assignments listed in your config file.
  5. Create the assignments listed in your config file in Canvas.
  6. Schedule automated grading of your assignments.
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
  :param args: Arguments passed in from the command line parser.

  First, initialize the course:
  0. Read your course configuration file and ensure all parameters are valid.
  1. Identify the tool name used for your JupyterHub installation in Canvas.
  2. Pull your student list from Canvas.  
  3. Sync students & assignments between Canvas and nbgrader.

  Because course initialization instantiates Assignment objects, we can search
  for our assignment by name.

  Next, start grading:
  1. Collect assignments
  2. Grade assignments
  3. If no manual input, generate forms
  4. If no manual input, return forms and submit grades
    TODO: Use Canvas File Upload API to upload feedback forms along with grades.
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

  First, initialize the course:
  0. Read your course configuration file and ensure all parameters are valid.
  1. Identify the tool name used for your JupyterHub installation in Canvas.
  2. Pull your student list from Canvas.  
  3. Sync students & assignments between Canvas and nbgrader.

  Because course initialization instantiates Assignment objects, we can search
  for our assignment by name.

  Next:
  1. Generate forms
  2. Return forms and submit grades
    TODO: Use Canvas File Upload API to upload feedback forms along with grades.
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
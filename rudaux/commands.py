from rudaux import Course, Assignment


def initialize_course(args):
  """Initialize a course fully. This involves:
  0. Reading your configuration file and ensuring all parameters are valid.
  1. Identifying the tool name used for your JupyterHub installation in Canvas.
  2. Pulling your student list from Canvas.  
  3. Syncing Canvas with nbgrader (students & assignments).
  4. Assigning all of the assignments listed in your config file.
  5. Creating the assignments listed in your config file in Canvas.
  6. Schedule automated grading of your assignments.
  """

  course = Course()

  course                         \
    .get_external_tool_id()      \
    .get_students_from_canvas()  \
    .sync_nbgrader()             \
    .assign_all(args.overwrite)  \
    .create_canvas_assignments() \
    .schedule_grading()


def schedule_grading(args):

  course = Course()

  course.schedule_grading()
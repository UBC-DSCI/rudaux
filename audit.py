from rudaux import Course, Assignment

course = Course(course_dir='/Users/samhinshaw/projects/dsci100/DSCI_100_instructors')

course                         \
  .get_external_tool_id()      \
  .get_students_from_canvas()  \
  .sync_nbgrader()             \
  .assign_all(overwrite=True)  \
  .create_canvas_assignments()
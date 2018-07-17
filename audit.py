# import unittest
from course import Course

course = Course(5394, 'https://ubc.test.instructure.com/')

# course.get_students()
# course.get_students().autograde('Alpha Romeo Tango Niner')

course.get_assignments_from_canvas()
# course.getAssignments().schedule_grading()

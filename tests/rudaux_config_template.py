import notification

c.name = 'course_name'
c.canvas_domain = 'https://canvas.ubc.ca'
c.canvas_id = '12345678'
c.canvas_token = 'instructor_canvas_token'
c.student_folder_root = '/absolute/path/where/student/folders/are/located'
c.assignment_folder_root = 'relative/path/inside/each/student/folder/where/assignments/are/located'
c.nbgrader_root = '/absolute/path/to/nbgrader/course/directory/'
c.zfs_snapshot_prefix = 'zfs-auto-snap-'
c.grading_image = 'docker_image_name'
c.state_file = 'course_state_file.pk'
c.course_admin = 'instructor_user_id'

c.notification_method = notification.SMTP
c.smtp.hostname = 'smtp.hostname.com:587'
c.smtp.address = 'address@hostname.com'
c.smtp.username = 'smtp_username'
c.smtp.passwd = 'smtp_password'
c.smtp.contact_info = {
   'ta_user_id' : 'TA_email@gmail.com',
   'instructor_user_id' : 'Instructor_email@ubc.ca'
}

c.nbgrader_graded_assignments = {
    'canvas_assignment_name' : {'graders' : ['grader_user_id', 'grader_user_id']}
}

c.nbgrader_ungraded_assignments = [
    'canvas_assignment_name'
]

c.ungraded_assignment_soln_release_days = 1

#c.extensions = {
#		'student_id' : {'canvas_assignment_to_be_extended' : 'future_canvas_assignment_to_make_the_new_deadline',
#				'canvas_assignment' : 'canvas_assignment'
#                               }
#}
                       

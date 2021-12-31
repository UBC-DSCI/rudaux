# the base domain for canvas at your institution
# e.g. at UBC, this is https://canvas.ubc.ca
c.canvas_domain = 'https://canvas.your-domain.com'

# tells rudaux which courses are part of which groups
# group_name is a simple name for the group of canvas courses.
# e.g.
# "dsci100" : ["12345", "678910"]
# "stat201" : ["54323"]
c.course_groups = {
    'group_name': ['canvas_id_1', 'canvas_id_2']
}

# tells rudaux what to call each course when printing to logs
# canvas_id_1/2/etc are the same as above
# human_readable_name_1/2/etc is just a human-readable name for each section
# (e.g., human_readable_name_1 and 2 would be dsci100-001 and dsci100-004 for 
# the two dsci100 sections)
# make sure you include names for every canvas ID above
# e.g.
# {"12345" : "dsci100-001", "678910" : "dsci100-004"}
c.course_names = {
    'canvas_id_1': 'human_readable_name_1', 
    'canvas_id_2': 'human_readable_name_2',
}

# tells rudaux the last day students have to add a course. 
# at UBC we can check it here:
# https://students.ubc.ca/enrolment/registration/course-change-dates
c.registration_deadline = '2022-01-21'

# gives rudaux the ability to read/write to canvas page
# canvas_id_1/2/etc are same as above
# instructor_token_1/2/etc are the Canvas API tokens for the instructor of each section
# make sure to include an instructor token for each canvas ID above
# i.e. if both sections have the same instructor, they'll have the same token
# e.g. {"12345" : "43456~34f8h948fha948haoweifha30948fha34f",  "678910": "54698~34hs384he4fhsoeirfho348hfaoweifh"}
c.course_tokens = {
	'canvas_id_1' : 'instructor_token_1',
	'canvas_id_2' : 'instructor_token_2',
}

# tells rudaux which assignments to track and who is grading them
# group_name same as above
# assignment_name_1/2/3 are assignment names from Canvas
# grader_jhub_username_A/B/etc are the grading jupyterhub username of TAs / instructors / whoever is responsible for grading
# if an assignment is purely autograded, just use the instructor's jhub username (no manual grading required)
# if multiple graders are listed with an assignment, rudaux splits the grading up for them equally 
c.assignments = {
	'group_name' : {
    	'assignment_name_1' : ['grader_jhub_username_A'], 
    	'assignment_name_2' : ['grader_jhub_username_B'],
    	'assignment_name_3' : ['grader_jhub_username_A', 'grader_jhub_username_B']
	}
}

# tells rudaux where to look for student work (usually a remote machine)
# canvas_id_1/2/etc are same canvas IDs as above
# hostname is the ssh hostname for the student machine
# port is the ssh port (usually just 22)
# admin_user is the linux user on the student machine to ssh into, should have admin privileges (needs to zfs snapshot)
# /usr/sbin/zfs is the path to the zfs exec, but change if needed
# /path/to/student/folder/directory is the dir with the student folders in it (e.g. /tank/home/dsci100/)
# make sure to include an entry below for each course (canvas_id_1/2/etc)
c.student_ssh = {
	'canvas_id_1' : {'hostname': 'student-jhub.com',
			'port': 22,
			'user' : 'admin_user',
			'zfs_path' : '/usr/sbin/zfs',
			'student_root' : '/path/to/student/folder/directory/'},
	'canvas_id_2' : {'hostname': 'maybe-another-student-jhub.com',
			'port': 22,
			'user' : 'admin_user',
			'zfs_path' : '/usr/sbin/zfs',
			'student_root' : '/path/to/other/student/folder/directory'},
}

# number of late registration automatic extension days (applies for all courses in each group)
c.latereg_extension_days = {
	'group_name' : 7
}

# timezone to use for sending grading notifications for outstanding tasks (posting grades, manual grading)
c.notify_timezone = 'America/Vancouver'

# days to send grading notifications (only a few days per week to avoid spamming the graders)
c.notify_days = ['Friday', 'Monday']

# email address to use for sending automated notifications
c.sendmail.address = 'rudaux@your-domain.com'

# email addresses to send notifications to
c.sendmail.contact_info = {
    'grader_jhub_username_A'  : {'name' : 'Bob', 'address' : 'bob@email.com'},
    'grader_jhub_username_B'  : {'name' : 'Alice', 'address' : 'alice@email.com'}
}

# specify which user is the instructor (who to notify to post grades)
# template below is if the course instructor's username on the grading jhub is grader_jhub_username_A
c.instructor_user = 'grader_jhub_username_A'

# specify where to find the jupyterhub config directory (rudaux manages grading jupyterhub accounts)
# you probably don't need to change this
c.jupyterhub_config_dir = '/srv/jupyterhub/'

# specify the linux user and group to grant ownership for grading directories (the jupyterhub user)
# you probably don't need to change this
c.jupyterhub_user = 'jupyter'
c.jupyterhub_group = 'users'

# specify the quota to give grading accounts
# default to 5 gigabytes, but you can make this larger/smaller as needed
c.user_quota = '5g'

# specify where to create new grading folders (path to the directory where the jupyterhub user folders are stored)
c.user_root = '/path/to/jhub/user/folder/dir'

# specify the names of submitted/feedback/autograded folders
# you probably don't need to change these
c.submissions_folder = 'submitted'
c.feedback_folder = 'feedback'
c.autograded_folder = 'autograded'

# the path to the ZFS exec on the grading machine
# you probably don't need to change this
c.zfs_path = '/usr/sbin/zfs'

# the ssh-access git repository URL (the root of this directory should be an nbgrader dir)
c.instructor_repo_url = 'git@github.com/your-instructor-repo.git'

# NFS mount of student jhub user directory to instructor machine
# NOTE: I believe this is no longer used. But leaving it in for now and will make a github issue to remove it.
c.student_dataset_root = '/path-student/to/jhub/user/folder/directory'

# the path in each student's JHub directory to look for their assignment folders
# e.g. if assignment_name_1's folder is located at dsci-100-student/materials/assignment_name_1/... within each student's jhub user folder (and similar for the other asgns),
# this would be "dsci-100-student/materials"
c.student_local_assignment_folder = 'dsci-100-student/materials'

# the prefix to add to user folders (nbgrader breaks with student folders that are just numbers, so append student-##### to make it work)
# this can be essentially anything as long as it starts with a letter, so you probably don't need to change this
c.grading_student_folder_prefix = 'student-'

# the fraction of deadlines that must be passed before solutions are returned (useful for early weeks in a semester with lots of auto late extensions)
c.return_solution_threshold = 0.93

# the earliest date to return solutions to anything regardless of the return thresholds
c.earliest_solution_return_date = '2021-09-26'

# the amount of memory to give each autograding container
c.docker_memory = '2g'

# the image to use for nbgrader operations
# the example below is for the 0.17.0 version of the DSCI100 image
c.docker_image = 'ubcdsci/r-dsci-grading:v0.17.0'

# the name of the directory in the container to bind to the grader's jhub folder
c.docker_bind_folder = '/home/jupyter'

# the minute and interval to run the autoextension/snapshot/grading flows
# e.g. below for snapshot would run at 1:02, 1:17, 1:32, ...
# similar behaviour for the other two
# typically grading flow runs much slower than the other two
c.snapshot_interval = 15
c.snapshot_minute = 2
c.autoext_interval = 60
c.autoext_minute = 0
c.grade_interval = 60*24
c.grade_minute = 10

# whether to run the flow once or on the usual schedule  (True = run once now, False = run on the normal schedule)
c.debug = True




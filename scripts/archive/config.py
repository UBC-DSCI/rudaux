#course

def course_config():
    config = {}
    config['hostname'] = 'https://canvas.ubc.ca'
    config['course_id'] = '2039048'
    with open('token.txt') as reader:
        config['token'] = reader.read()
    
    ##config['']
    return config

# dsci100['name'] = 'DSCI 100'
# dsci100['token'] = os.environ['CANVAS_TOKEN']
# dsci100['course_storage_path'] = '/tank/home/dsci100'
# dsci100['student_assignment_path'] = 'dsci-100/materials'
# dsci100['instructor_repo_path'] = 'dsci-100-instructor'
# dsci100['student_name_prefix'] = 'student_'
# dsci100['gradebook_filename'] = 'gradebook.db'
# dsci100['backup_folder_name'] = 'backups'
# dsci100['grader_allocations_file'] = 'allocations.pk'
# dsci100['instructor_submitted_path'] = os.path.join(dsci100['instructor_repo_path'], 'submitted')
# dsci100['instructor_release_path'] = os.path.join(dsci100['instructor_repo_path'], 'release')
# dsci100['instructor_source_folder'] = 'source'
# dsci100['instructor_autograded_path'] = os.path.join(dsci100['instructor_repo_path'], 'autograded')
# dsci100['instructor_feedback_path'] = os.path.join(dsci100['instructor_repo_path'], 'feedback')
# dsci100['snapshot_prefix'] = 'zfs-auto-snap-'
# dsci100['snapshot_minute'] = 10
# dsci100['snapshot_hour'] = 6
# dsci100['snapshot_days'] = [6, 3] #sunday, thursday (python datetime format is mon = 0, sun = 6; NB, linux datetime format is 1-7!)
# dsci100['student_server_hostname'] = '[STU_SERVER_HOSTNAME]'
# dsci100['student_server_username'] = '[STU_SERVER_USERNAME]'

# dsci100['autograded_assignments'] = {
#            'worksheet_01' : {'graders' : ['[INSTRUCTOR_CWL]'], 'instructor' : '[INSTRUCTOR_CWL]'},
#            'tutorial_01' : {'graders' : ['[TA_CWL]', '[TA_CWL]'], 'instructor' : '[INSTRUCTOR_CWL]'}
# 	   }# question: we would add entries to the list of assignments at the moment?

# dsci100['ungraded_assignments'] = {
#            'worksheet_activity_02' : '[INSTRUCTOR_CWL]',
#            }
# dsci100['ungraded_assignment_solution_release_days'] = 1

# dsci100['emails'] = {
#             '[INSTRUCTOR_CWL]' : '[INSTRUCTOR_EMAIL]',
#             '[INSTRUCTOR_CWL]' : '[INSTRUCTOR_EMAIL]',
#             '[TA_CWL]' : '[TA_EMAIL]'
#           }

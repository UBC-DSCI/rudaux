#this script is called by cron once a day 
#it decides whether there is anything new to autograde, autogrades it, and decides when to return grades / feedback / solutions / etc
import os
import smtplib
import canvas
import pandas
import datetime
import paramiko # ssh stuff, use shutil instead
import numpy as np
import smtplib
import shutil
import subprocess #docker stuff - use docker api instead
import hashlib
import pickle as pk
from nbgrader.api import Gradebook, MissingEntry
from nbgrader.apps import NbGraderAPI
import json

#config for dsci100
dsci100 = {}
dsci100['name'] = 'DSCI 100'
dsci100['hostname'] = 'https://canvas.ubc.ca'
dsci100['course_id'] = '[CANVAS_COURSE_ID_NUM]'
dsci100['token'] = os.environ['CANVAS_TOKEN']
dsci100['course_storage_path'] = '/tank/home/dsci100'
dsci100['student_assignment_path'] = 'dsci-100/materials'
dsci100['instructor_repo_path'] = 'dsci-100-instructor'
dsci100['student_name_prefix'] = 'student_'
dsci100['gradebook_filename'] = 'gradebook.db'
dsci100['backup_folder_name'] = 'backups'
dsci100['grader_allocations_file'] = 'allocations.pk'
dsci100['instructor_submitted_path'] = os.path.join(dsci100['instructor_repo_path'], 'submitted')
dsci100['instructor_release_path'] = os.path.join(dsci100['instructor_repo_path'], 'release')
dsci100['instructor_source_folder'] = 'source'
dsci100['instructor_autograded_path'] = os.path.join(dsci100['instructor_repo_path'], 'autograded')
dsci100['instructor_feedback_path'] = os.path.join(dsci100['instructor_repo_path'], 'feedback')
dsci100['snapshot_prefix'] = 'zfs-auto-snap-'
dsci100['snapshot_minute'] = 10
dsci100['snapshot_hour'] = 6
dsci100['snapshot_days'] = [6, 3] #sunday, thursday (python datetime format is mon = 0, sun = 6; NB, linux datetime format is 1-7!)
dsci100['student_server_hostname'] = '[STU_SERVER_HOSTNAME]'
dsci100['student_server_username'] = '[STU_SERVER_USERNAME]'

dsci100['autograded_assignments'] = {
           'worksheet_01' : {'graders' : ['[INSTRUCTOR_CWL]'], 'instructor' : '[INSTRUCTOR_CWL]'},
           'tutorial_01' : {'graders' : ['[TA_CWL]', '[TA_CWL]'], 'instructor' : '[INSTRUCTOR_CWL]'}
	   }# question: we would add entries to the list of assignments at the moment?

dsci100['ungraded_assignments'] = {
           'worksheet_activity_02' : '[INSTRUCTOR_CWL]',
           }
dsci100['ungraded_assignment_solution_release_days'] = 1

dsci100['emails'] = {
            '[INSTRUCTOR_CWL]' : '[INSTRUCTOR_EMAIL]',
            '[INSTRUCTOR_CWL]' : '[INSTRUCTOR_EMAIL]',
            '[TA_CWL]' : '[TA_EMAIL]'
          }

#replace due date of assignment with future assignment
dsci100['extensions'] = {
            '[STUDENT_CANVAS_ID]' : {'worksheet_03' : 'worksheet_04',
                        'tutorial_03' : 'worksheet_04'
                       },
            '[STUDENT_CANVAS_ID]' : {'tutorial_07' : 'worksheet_08'
                       }
}

def ssh_student_hub(course): ##TODO checkout paramiko documents
  ssh = paramiko.SSHClient() 
  ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  ssh.connect(course['student_server_hostname'], username=course['student_server_username'])
  return ssh

def ssh_run_cmd(cxn, cmd): 
  (stdin, stdout, stderr) = cxn.exec_command(cmd)
  for line in stdout.readlines():
      print(line)
  for line in stderr.readlines():
      print(line)

#need this function to deal with github issue 
#https://github.com/jupyter/nbgrader/issues/1083
def remove_duplicate_grade_ids(course, anm, stu, grader):
  submitted_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.ipynb')
  #open the student's notebook
  f = open(submitted_path, 'r')
  nb = json.load(f)
  f.close()

  #go through and delete the nbgrader metadata from any duplicated cells
  cell_ids = set()
  for cell in nb['cells']:
    try:
      cell_id = cell['metadata']['nbgrader']['grade_id']
    except:
      continue
    if cell_id in cell_ids:
      print('Student ' + stu + ' assignment ' + anm + ' grader ' + grader + ' had a duplicate cell! ID = ' + str(cell_id))
      print('Removing the nbgrader metainfo from that cell to avoid bugs in autograde')
      cell['metadata'].pop('nbgrader', None)
    else:
      cell_ids.add(cell_id)

  #write the sanitized notebook back to the submitted folder
  f = open(submitted_path, 'w')
  json.dump(nb, f)
  f.close()

def check_submission_exists(course, anm, stu, grader):
  submitted_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.ipynb')
  return os.path.exists(submitted_path)
  


def collect_assignment(course, anm, due_date_time, stu, grader, sftp):
  #create the remote snapshot path suffix (same for every student)
  remote_snapshot_path_suffix = os.path.join('.zfs', 
                                      'snapshot', 
                                      course['snapshot_prefix'] + due_date_time,
                                      course['student_assignment_path'],
                                      anm,
                                      anm+'.ipynb')
  print('Remote path suffix: ' + str(remote_snapshot_path_suffix))
  
  local_submitted_path_prefix = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'])
  print('Local path prefix: ' + str(local_submitted_path_prefix))

  local_student_assignment_folder = os.path.join(local_submitted_path_prefix, course['student_name_prefix']+stu, anm)
  if not os.path.exists(local_student_assignment_folder):
    os.makedirs(local_student_assignment_folder, exist_ok=True)
  
  assignment_path_local = os.path.join(local_student_assignment_folder, anm+'.ipynb')

  if not os.path.exists(assignment_path_local):
    assignment_path_remote = os.path.join(course['course_storage_path'], stu, remote_snapshot_path_suffix)
     
    #copy the hub-prod version of the file if it exists; if not, do nothing
    try:
        sftp.get(remotepath=assignment_path_remote, localpath=assignment_path_local)
    except IOError as e:
        print('IOError when copying from the remote path at')
        print(assignment_path_remote)
        print('IOError Message:')
        print(e)
        #if the resulting .ipynb file is empty, delete the student's path so autograder doesn't fail
        if not os.path.getsize(assignment_path_local):
            print('copied assignment was empty, deleting folder')
            shutil.rmtree(local_student_assignment_folder)

def generate_assignment(course, anm, grader):
  #create the local path 
  local_repo_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])

  print('Running a docker container to check if assignment ' + anm + ' exists for ' + grader)
  docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader db assignment list'
  print(docker_command)
  result = str(subprocess.check_output(docker_command.split(' ')))
  print('Result:')
  print(result)
  if anm not in result:
    print('Need to generate assignment ' + anm + ' for grader ' + grader)
    docker_command = 'docker run --rm -v ' + local_repo_path +':/home/jupyter ubcdsci/r-dsci-grading nbgrader generate_assignment --force ' + anm
    print(docker_command)
    subprocess.check_output(docker_command.split(' '))


def autograde_assignment(course, anm, stu, grader):
 #one submission at a time. DO NOT run more than 1 submission at a time.
 #ideally: 1 container, but within 1 container, grade all submissions 1 by 1, and then close the container 
  autograded_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_autograded_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.ipynb')
  
  #only run the autograder if the student actually submitted something + it isn't autograded yet
  if not os.path.exists(autograded_path):
    #create a docker container that autogrades the assignment for the grader
    print('Running a docker container to autograde assignment ' + anm + ' for student ' + stu + ' as grader ' + grader)
    local_repo_path_prefix = os.path.join(course['course_storage_path'], 
                                        grader,
                                        course['instructor_repo_path'])
    docker_command = 'docker run --rm -v ' + local_repo_path_prefix +':/home/jupyter ubcdsci/r-dsci-grading nbgrader autograde --assignment=' + anm + ' --student='+course['student_name_prefix']+stu
    print(docker_command)
    subprocess.check_output(docker_command.split(' '))
  else:
    print('Student ' + stu + ' assignment ' + anm + ' already autograded. Skipping autograde.')

def generate_feedback(course, anm, stu, grader):
  #create a docker container that generates fdbk
  print('Running a docker container to generate feedback for assignment ' + anm + ' student ' + stu)
  local_repo_path_prefix = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])
  docker_command = 'docker run --rm -v ' + local_repo_path_prefix +':/home/jupyter ubcdsci/r-dsci-grading nbgrader generate_feedback --force --assignment=' + anm + ' --student='+course['student_name_prefix']+stu
  print(docker_command)
  subprocess.check_output(docker_command.split(' '))

def generate_solution(course, anm, grader):
  #create a docker container that generates the solution html
  print('Running a docker container to generate solution for assignment ' + anm)
  local_repo_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])
  local_notebook_path = os.path.join(course['instructor_source_folder'], anm, anm+'.ipynb')
  docker_command = 'docker run --rm -v ' + local_repo_path + ':/home/jupyter ubcdsci/r-dsci-grading jupyter nbconvert ' + local_notebook_path + ' --output=' + anm +'_solution.html --output-dir=.'
  print(docker_command)
  subprocess.check_output(docker_command.split(' '))

def return_feedback(course, anm, stu, grader, sftp, ssh):
  
  student_folder_remote = os.path.join(course['course_storage_path'], stu)
  
  feedback_folder_remote = os.path.join(student_folder_remote, 'feedback')
  
  feedback_file_remote = os.path.join(feedback_folder_remote, anm+'.html')

  feedback_file_local = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_feedback_path'],
                                      course['student_name_prefix'] + stu, 
                                      anm,
                                      anm + '.html')

  print('student folder remote: ' + student_folder_remote)
  print('feedback folder remote: ' + feedback_folder_remote)
  print('feedback file remote: ' + feedback_file_remote)
  print('feedback file local: ' + feedback_file_local)

  #make sure the student folder has write permissions for the group jupyter
  try:
      #sftp.chmod(student_folder_remote, 775)
      ssh_run_cmd(ssh, 'sudo chmod g+w ' + student_folder_remote)
      print('set student folder permissions to rwxrwxr-x')
  except IOError as e:
      print(e)

  #create /tank/home/dsci100/#####/feedback
  try:
      sftp.mkdir(feedback_folder_remote)
      #sftp.chown(feedback_folder_remote, 'jupyter', 'users')
      ssh_run_cmd(ssh, 'sudo chown jupyter:jupyter ' + feedback_folder_remote)
      print('created folder ' + feedback_folder_remote)
  except IOError as e:
      print(e)
  #create /tank/home/dsci100/#####/feedback/assignment.html
  try:
      sftp.put(localpath=feedback_file_local, remotepath=feedback_file_remote)
      #sftp.chown(feedback_file_remote, 'jupyter', 'users')
      ssh_run_cmd(ssh, 'sudo chown jupyter:users ' + feedback_file_remote)
      print('copied ' + feedback_file_local + ' to ' + feedback_file_remote)
  except IOError as e:
      print(e)

def return_solution(course, anm, stu, grader, sftp, ssh):
  
  student_folder_remote = os.path.join(course['course_storage_path'], stu)
  
  feedback_folder_remote = os.path.join(student_folder_remote, 'feedback')
  
  solution_file_remote = os.path.join(feedback_folder_remote, anm+'_solution.html')

  solution_file_local = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'],
                                      anm + '_solution.html')

  print('student folder remote: ' + student_folder_remote)
  print('feedback folder remote: ' + feedback_folder_remote)
  print('solution file remote: ' + solution_file_remote)
  print('solution file local: ' + solution_file_local)

  #make sure the student folder has write permissions for the group jupyter
  try:
      #sftp.chmod(student_folder_remote, 775)
      ssh_run_cmd(ssh, 'sudo chmod g+w ' + student_folder_remote)
      print('set student folder permissions to rwxrwxr-x')
  except IOError as e:
      print(e)

  #create /tank/home/dsci100/#####/feedback
  try:
      sftp.mkdir(feedback_folder_remote)
      #sftp.chown(feedback_folder_remote, 'jupyter', 'users')
      ssh_run_cmd(ssh, 'sudo chown jupyter:jupyter ' + feedback_folder_remote)
      print('created folder ' + feedback_folder_remote)
  except IOError as e:
      print(e)
  #create /tank/home/dsci100/#####/feedback/assignment_solution.html
  try:
      sftp.put(localpath=solution_file_local, remotepath=solution_file_remote)
      #sftp.chown(feedback_file_remote, 'jupyter', 'users')
      ssh_run_cmd(ssh, 'sudo chown jupyter:users ' + solution_file_remote)
      print('copied ' + solution_file_local + ' to ' + solution_file_remote)
  except IOError as e:
      print(e)

def check_needs_manual_grading(course, anm, stu, grader):
  gradebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'],
                                      course['gradebook_filename'])
  gb = Gradebook('sqlite:///'+gradebook_file)

  try:
    subm = gb.find_submission(anm, course['student_name_prefix']+stu)
    flag = subm.needs_manual_grade
  except MissingEntry as e:
    print(e)
  finally:
    gb.close()

  return flag

def upload_grade(course, anm, stu, grader):
  print('Getting grade for student ' + stu + ' assignment ' + anm)
  course_dir_path = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'])

  gradebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_repo_path'],
                                      course['gradebook_filename'])
  gb = Gradebook('sqlite:///'+gradebook_file)

  try:
    subm = gb.find_submission(anm, course['student_name_prefix']+stu)
    score = subm.score
  except MissingEntry as e:
    print(e)
  finally:
    gb.close()
  max_score = compute_max_score(course, anm, grader)

  print('Student ' + stu + ' assignment ' + anm + ' score: ' + str(score))
  print('Assignment ' + anm + ' max score: ' + str(max_score))
  print('Pct Score: ' + str(100*score/max_score))
  print('Posting to canvas...')
  canvas.post_grade(course, anm, stu, str(100*score/max_score))

def compute_max_score(course, anm, grader):
  #for some incredibly annoying reason, nbgrader refuses to compute a max_score for anything (so we cannot easily convert scores to percentages)
  #let's compute the max_score from the notebook manually then....

  release_notebook_file = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_release_path'],
                                      anm,
                                      anm+'.ipynb')
  f = open(release_notebook_file, 'r')
  parsed_json = json.load(f)
  f.close()
  pts = 0
  for cell in parsed_json['cells']:
    try:
      pts += cell['metadata']['nbgrader']['points']
    except Exception as e:
      #will throw exception if cells dont exist / not right type -- that's fine, it'll happen a lot.
      pass
  return pts

def backup_grades(course):
  try:
    if not os.path.exists(course['backup_folder_name']):
      print('Creating backup folder')
      os.mkdir(course['backup_folder_name'])
  except:
    pass
  gradebk = {}
  for anm in course['autograded_assignments'].keys():
    print('Getting grades for ' + anm)
    asgnmt_grades = canvas.get_grades(course, anm)
    gradebk[anm] = asgnmt_grades
  gfn = os.path.join(course['backup_folder_name'], 'gradebook_backup_'+datetime.datetime.today().strftime('%Y_%m_%d_%H_%M')+'.pk')
  print('Pickling gradebook to ' + gfn)
  f = open(gfn, 'wb')
  pk.dump(gradebk, f)
  f.close()

def backup_gradebooks(course):
  try:
    if not os.path.exists(course['backup_folder_name']):
      print('Creating backup folder')
      os.mkdir(course['backup_folder_name'])
  except:
    pass
  for grader in course['emails']:
    grader_gradebook_fn = os.path.join(course['course_storage_path'], 
                                       grader,
                                       course['instructor_repo_path'],
                                       course['gradebook_filename'])
    backup_gradebook_fn = os.path.join(course['backup_folder_name'],
                                       grader+'_'+datetime.datetime.today().strftime('%Y_%m_%d_%H_%M')+'_'+course['gradebook_filename'])
    print('Backing up ' + grader_gradebook_fn + ' to ' + backup_gradebook_fn)
    if os.path.exists(grader_gradebook_fn):
      shutil.copy(grader_gradebook_fn, backup_gradebook_fn)
    else:
      print('No ' + course['gradebook_filename'] + ' in ' + grader + 's folder.')

#def get_grader(course, anm, stu):
#  #use hashing to choose the grader (doesn't depend on splitting a list of students, which can change over time)
#  max_idx = np.argmax([int(hashlib.md5((stu + anm + grdr).encode('utf-8')).hexdigest(), 16) for grdr in course['autograded_assignments'][anm]['graders']])
#  return course['autograded_assignments'][anm]['graders'][max_idx]

def dispatch(course):

  #Dispatch Begin (this runs every night at midnight / 1am (depending on daylight savings)
  print('Running ' + course['name'] + ' Dispatch')

  print('Backing up course gradebook')
  backup_grades(course)

  print('Backing up grader databases')
  backup_gradebooks(course)

  #get full list of assignments
  print('Getting assignment list from Canvas')
  all_assignments = canvas.get_assignments(course)
  #filter to those that are in the list of things to autograde
  assignments = all_assignments[all_assignments['name'].isin(course['autograded_assignments'].keys())]
  assignments = [assignments['name'].values[ii] for ii in range(assignments.shape[0])]
  ungraded_assignments = all_assignments[all_assignments['name'].isin(course['ungraded_assignments'].keys())]
  ungraded_assignments = [ungraded_assignments['name'].values[ii] for ii in range(ungraded_assignments.shape[0])]

  print('Getting student enrollment dates from Canvas')
  enrollment_dates = canvas.get_enrollment_dates(course)

  print('Opening SSH / SFTP connection to student hub')
  ssh = ssh_student_hub(course)
  sftp = ssh.open_sftp() 

  #create a dict of graders + assignments that require their manual grading
  grader_notifications = {}
  instructor_notifications = {}

  print('Processing assignments')
  for anm in assignments:
    #get the due date for this assignment (or None for any assignment w/o a due date)
    print('Checking if ' + anm + ' was due previously')
    due_date = canvas.get_assignment_due_date(course, anm)
    unlock_date = canvas.get_assignment_unlock_date(course, anm)

    if due_date is None or unlock_date is None: 
      print('Due date / unlock date for ' + anm + ' is None -- please make sure a due date is set to a snapshot date/time, and unlock date is set to the start of the relevant class!') 
      continue

    unlock_datetime = datetime.datetime.strptime(unlock_date, '%Y-%m-%d-%H-%M')
    due_datetime = datetime.datetime.strptime(due_date, '%Y-%m-%d-%H-%M')
    snap_datetime = due_datetime.replace(hour=course['snapshot_hour'], minute=course['snapshot_minute'])
    
    #if the assignment is due in the future, skip it
    if snap_datetime >= datetime.datetime.today():
      continue

    print(anm + ' was due previously on ' + str(due_datetime) + ' with snapshot at ' + str(snap_datetime) )

    print('Getting students/grades list for ' + anm + ' from Canvas')
    #get list of grades for this assignment from Canvas
    grades = canvas.get_grades(course, anm) 

    print('Making sure each assigned grader has the assignment')
    for grader in course['autograded_assignments'][anm]['graders']:
      generate_assignment(course, anm, grader)

    print('Making sure each assigned grader has the solution file')
    for grader in course['autograded_assignments'][anm]['graders']:
      generate_solution(course, anm, grader)

    print('Allocating students to graders')
    if os.path.exists(course['grader_allocations_file']):
      f = open(course['grader_allocations_file'], 'rb')
      graders = pk.load(f)
      f.close()
    else:
      graders = {}
    if anm not in graders.keys():
      graders[anm] = {}
    idx = 0
    ngraders = len(course['autograded_assignments'][anm]['graders'])
    for stu in enrollment_dates.keys(): 
      if stu not in graders[anm].keys():
        graders[anm][stu] = course['autograded_assignments'][anm]['graders'][idx % ngraders]
        idx += 1
    f = open(course['grader_allocations_file'], 'wb')
    pk.dump(graders, f)
    f.close()

    #iterate over students to check if they've received a grade
    print('Checking grading status of each student for assignment '+anm)
    all_completed = True
    all_submitted = True
    for stu in enrollment_dates.keys(): 
      print('') #newline for each student
      grader = graders[anm][stu]
      print('Student ' + stu + ' assignment ' + anm + ' assigned to ' + grader + ' for grading.')

      enroll_datetime = datetime.datetime.strptime(enrollment_dates[stu], '%Y-%m-%d-%H-%M')

      extension_anm = None
      try:
        extension_anm = course['extensions'][stu][anm]
      except:
        pass

      #compute the student-specific due date (based on their registration date and custom extension; handles late regs)
      #basically: 
      #any student that registered after a class session has a due date of registration_date + 1 week
      #any student that registered before a class session has the regular deadline 
      #any student listed in the dsci100['extenstions'] object overrides with a custom date
      if extension_anm is not None:
        ext_due_date = canvas.get_assignment_due_date(course, extension_anm)

        if ext_due_date is None:
          print('Due date date for ' + anm + ' (extended to ' + extension_anm + ') is None -- please make sure a due date is set to a snapshot date/time!') 
          all_completed = False
          all_submitted = False
          continue

        ext_due_datetime = datetime.datetime.strptime(ext_due_date, '%Y-%m-%d-%H-%M')
        stu_snap_datetime = ext_due_datetime.replace(hour=course['snapshot_hour'], minute=course['snapshot_minute'])
        stu_snap_date = stu_snap_datetime.strftime('%Y-%m-%d-%H%M')
      elif enroll_datetime < unlock_datetime:
        #keep the usual deadline
        stu_snap_datetime = snap_datetime
        stu_snap_date = snap_datetime.strftime('%Y-%m-%d-%H%M')
      else:
        #give the student 1 week after reg
        stu_due_datetime = enroll_datetime + datetime.timedelta(days = 7)
        #find the next snapshot time after the student deadline (guaranteed to be at most a week after the stu_due_date, so initialize to days + 7)
        stu_snap_datetime = stu_due_datetime + datetime.timedelta(days = 14)
        for weekday in course['snapshot_days']:
          days_ahead = weekday - stu_due_datetime.weekday()
          if days_ahead < 0:
            days_ahead += 7
          snap_date_tmp = stu_due_datetime + datetime.timedelta(days_ahead)
          snap_date_tmp = snap_date_tmp.replace(hour = course['snapshot_hour'], minute = course['snapshot_minute'])
          if snap_date_tmp < stu_snap_datetime:
            stu_snap_datetime = snap_date_tmp
        stu_snap_date = stu_snap_datetime.strftime('%Y-%m-%d-%H%M')

      print('Student ' + stu + ' enrollment: ' + str(enroll_datetime))
      print('Assignment ' + anm + ' unlock: ' + str(unlock_datetime))
      print('Standard ' + anm + ' snapshot: ' + str(snap_datetime))
      if extension_anm is not None:
        print('Extension to ' + extension_anm + ' requested')
      print('Student ' + stu + ' snapshot: ' + str(stu_snap_datetime))

      if stu_snap_datetime > datetime.datetime.today():
        print('We havent reached the student snapshot datetime yet; skipping')
        all_completed = False
        all_submitted = False
        continue

      if grades[stu] is None:
        print('Student ' + stu + ' hasnt received a grade yet for ' + anm)
     
        #if it hasn't been sent to the grader yet, do so
        print('Collecting assignment if necessary')
        collect_assignment(course, anm, stu_snap_date, stu, grader, sftp)

        #only continue from here if we successfully copied an assignment
        if not check_submission_exists(course, anm, stu, grader):
          print('Collection failed; student did not submit on-time. Assigning 0.')
          canvas.post_grade(course, anm, stu, '0')
          continue

        #merging duplicate cells to deal with nbgrader issue 1083
        print('Removing duplicated cell_ids')
        remove_duplicate_grade_ids(course, anm, stu, grader)
        
        #if it hasn't been autograded yet, do so
        #must use a docker container for this, since we need to grade in the same environment as students worked in
        #i.e. can't use nbgrader api here :(
        print('Autograding assignment if necessary') 
        autograde_assignment(course, anm, stu, grader)
    
        #check the grader's db to see if the assignment needs manual grading
        if check_needs_manual_grading(course, anm, stu, grader):
          print('Student ' + stu + ' assignment ' + anm + ' still needs manual grading. Skipping grade upload')
          #add to grader's notifications
          if grader not in grader_notifications.keys():
            grader_notifications[grader] = set()
          grader_notifications[grader].add(anm)
          #this means we aren't done with grading this, so don't do feedback/solns yet
          all_completed = False
          continue

        ##generate feedback for the assignment
        print('Generating feedback for student ' + stu + ' assignment ' + anm)
        generate_feedback(course, anm, stu, grader)

        #upload grade for the assignment
        print('Uploading grade for student ' + stu + ' assignment ' + anm + ' to canvas')
        upload_grade(course, anm, stu, grader)

        print('Grading is complete for student ' + stu + ' assignment ' + anm)
      else:
        print('Student ' + stu + ' has already been graded for ' + anm + '; skipping')
        continue

    #if all auto+manual grading done, check if instructor posted grades; if not, ping the instructor
    #otherwise, send the feedback
    if all_completed:
      print('Grading for assignment ' + anm + ' is complete. Checking if grades still need posting on canvas...')
      if canvas.grades_need_posting(course, anm):
        print('Grades still need posting. Notifying instructor')
        #add to insrtuctor notifications to check over grades and post
        instructor = course['autograded_assignments'][anm]['instructor']
        if instructor not in instructor_notifications.keys():
          instructor_notifications[instructor] = set()
        instructor_notifications[instructor].add(anm)
      else:
        print('Grades for ' + anm + ' are all posted. Returning feedback')
        for stu in enrollment_dates.keys(): 
          grader = graders[anm][stu]
          #return the feedback for the assignment
          print('Returning feedback for student ' + stu + ' assignment ' + anm)
          return_feedback(course, anm, stu, grader, sftp, ssh)
    else:
      print('Not done grading all students for ' + anm + '. Waiting to return feedback...')

    if all_submitted:
      print('All students have submitted or missed the deadline for ' + anm + '. Returning solutions...')
      for stu in enrollment_dates.keys(): 
        grader = graders[anm][stu]
        #return the solution for the assignment
        print('Returning solution for student ' + stu + ' assignment ' + anm)
        return_solution(course, anm, stu, grader, sftp, ssh)
    else:
      print('Not passed submission deadline for all students for ' + anm + '. Waiting to return solns...')

    #make sure the submitted/ folder + contents are owned by jupyter:users (collect_assignment(...) makes them owned by root/root
    #it's way more annoying to do it in python (no recursive chown) so just do it via system command
    for grader in course['autograded_assignments'][anm]['graders']:
      local_submitted_folder = os.path.join(course['course_storage_path'], 
                                      grader,
                                      course['instructor_submitted_path'])
      print('Making sure submitted/ folder ownership is jupyter:users for grader ' + grader)
      subprocess.check_output(['chown', '-R', 'jupyter:users', local_submitted_folder])

  print('Processing ungraded assignments')
  for anm in ungraded_assignments:
    #get the due date for this assignment (or None for any assignment w/o a due date)
    print('Checking if ungraded ' + anm + ' was unlocked previously')
    unlock_date = canvas.get_assignment_unlock_date(course, anm)

    if unlock_date is None: 
      print('Unlock date for ungraded ' + anm + ' is None -- please make sure an unlock date is set to the start of the relevant class!') 
      continue

    unlock_datetime = datetime.datetime.strptime(unlock_date, '%Y-%m-%d-%H-%M')
    
    if unlock_datetime + datetime.timedelta(days = course['ungraded_assignment_solution_release_days']) >= datetime.datetime.today():
      continue

    print('Ungraded ' + anm + ' was unlocked previously on ' + str(unlock_datetime)) 

    print('Generating the solution file in the grader folder')
    generate_solution(course, anm, course['ungraded_assignments'][anm])

    print('Returning solution for ungraded ' + anm)
    grader = course['ungraded_assignments'][anm]
    for stu in enrollment_dates.keys(): 
      #return the solution for the assignment
      print('Returning solution for student ' + stu + ' ungraded assignment ' + anm)
      return_solution(course, anm, stu, grader, sftp, ssh)

  #close connections to student hub
  sftp.close()
  ssh.close()

  if len(grader_notifications.keys()) > 0 or len(instructor_notifications.keys()) > 0:
    #send notifications to instructors / graders
    email_hostname = '[SMTP_EMAIL_HOSTNAME]'
    email_address = '[EMAIL_ADDRESS]'
    email_username = '[SMTP_USERNAME]'
    email_pword = '[SMTP_PASSWORD]'
    print('Opening connection and logging in to email server')
    email_server = smtplib.SMTP(email_hostname)
    email_server.ehlo()
    email_server.starttls()
    email_server.login(email_username, email_pword)
    grader_message = '\r\n'.join(['From: '+email_address,
                                  'To: {}',
                                  'Subject: Manual grading needed',
                                  '',
                                  'Hi DSCI100 TA,',
                                  '',
                                  'You have an assigned manual grading task for assignments {} still open. Please log into our marking server and use the formgrader to grade these assignments.'
                                  '',
                                  'Thanks!',
                                  'DSCI100 Email Bot'])
    instructor_message = '\r\n'.join(['From: '+email_address,
                                  'To: {}',
                                  'Subject: Grading complete; checks needed',
                                  '',
                                  'Hi DSCI100 Instructor,',
                                  '',
                                  'Assignments {} now have all grades assigned. They are not yet posted; please visit Canvas to check the numbers and manually post them.',
                                  '',
                                  'Thanks!',
                                  'DSCI100 Email Bot'])
    for grader in grader_notifications.keys():
      print('Sending message to ' + grader + ' about grading ' + ', '.join(grader_notifications[grader]))
      email_server.sendmail(email_address, course['emails'][grader], grader_message.format(course['emails'][grader], ', '.join(grader_notifications[grader])))
    for instructor in instructor_notifications.keys():
      print('Sending message to ' + instructor + ' about posting grades for ' + ', '.join(instructor_notifications[instructor]))
      email_server.sendmail(email_address, course['emails'][instructor], instructor_message.format(course['emails'][instructor], ', '.join(instructor_notifications[instructor])))
    email_server.quit()
  
dispatch(dsci100)

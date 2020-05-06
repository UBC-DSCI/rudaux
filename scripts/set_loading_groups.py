import requests
import sys
import argparse
import urllib.parse
import posixpath
import pandas as pd
import canvas
import os
import datetime
import json

def get_group_users(course, gid):
    '''Takes a course object and group and returns a list of users. 

    Example:
    course.get_enrollment_date()'''
    url_path = posixpath.join("api", "v1", "groups", gid, 'users')
    api_url = urllib.parse.urljoin(course['hostname'], url_path)
    token = course['token']
    resp = None
    users = []
    while resp is None or resp.links['current']['url'] != resp.links['last']['url']:
      resp = requests.get(
          url = api_url if resp is None else resp.links['next']['url'],
          headers = {
              "Authorization": f"Bearer {token}",
              },
          json={
            "per_page":"100"
          }
      )
      users.extend(resp.json())
    return users


def get_groups(course):
    '''Takes a course object and returns a list of groups. 

    Example:
    course.get_enrollment_date()'''
    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "groups")
    api_url = urllib.parse.urljoin(course['hostname'], url_path)
    token = course['token']
    resp = None
    groups = []
    while resp is None or resp.links['current']['url'] != resp.links['last']['url']:
      resp = requests.get(
          url = api_url if resp is None else resp.links['next']['url'],
          headers = {
              "Authorization": f"Bearer {token}",
              },
          json={
            "per_page":"100"
          }
      )
      groups.extend(resp.json())
    return groups

def get_assignment_overrides(course, aid):
    '''Takes a course object and returns a list of groups. 

    Example:
    course.get_enrollment_date()'''
    url_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", aid, 'overrides')
    api_url = urllib.parse.urljoin(course['hostname'], url_path)
    token = course['token']
    resp = None
    return requests.get(
          url = api_url,
          headers = {
              "Authorization": f"Bearer {token}",
              },
          json={
            "per_page":"100"
          }
      ).json()

def set_assignment_dates(course, aid, uids, title, unlock_timestamp, due_timestamp, lock_timestamp):
    '''Takes a course object, an assignment name, student id, and score to upload. Posts to Canvas.

    Example:
    course.post_grades(dsci100, 'worksheet_01', '23423', 10)'''
    url_post_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", aid, "overrides")
    api_url = urllib.parse.urljoin(course['hostname'], url_post_path)
    token = course['token']
    resp = requests.post(
        url = api_url,
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
            },
        json={
            "assignment_override" : {"student_ids": uids, "unlock_at": unlock_timestamp, "due_at" : due_timestamp, "lock_at" : lock_timestamp, "title" : title}
            }
    )
    print(resp)

def delete_override(course, aid, oid):
    '''Takes a course object, an assignment name, student id, and score to upload. Posts to Canvas.

    Example:
    course.post_grades(dsci100, 'worksheet_01', '23423', 10)'''
    url_post_path = posixpath.join("api", "v1", "courses", course['course_id'], "assignments", aid, "overrides", oid)
    api_url = urllib.parse.urljoin(course['hostname'], url_post_path)
    token = course['token']
    resp = requests.delete(
        url = api_url,
        headers = {
            "Authorization": f"Bearer {token}",
            }
    )
    print(resp)

dsci100 = {}
dsci100['name'] = 'DSCI 100'
dsci100['hostname'] = 'https://canvas.ubc.ca'
dsci100['course_id'] = '[COURSE_ID_NUM]'
dsci100['token'] = os.environ['CANVAS_TOKEN']

delay_hours = 2
assignment_name = sys.argv[1]
assignment_id = canvas.get_assignment_id(dsci100, assignment_name)

unlock_datetime = datetime.datetime.strptime(canvas.get_assignment_unlock_date(dsci100, assignment_name), '%Y-%m-%d-%H-%M')
future_unlock_datetime = unlock_datetime + datetime.timedelta(hours = delay_hours)
future_unlock_timestamp = future_unlock_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

lock_datetime = datetime.datetime.strptime(canvas.get_assignment_lock_date(dsci100, assignment_name), '%Y-%m-%d-%H-%M')
lock_timestamp = lock_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

due_datetime = datetime.datetime.strptime(canvas.get_assignment_due_date(dsci100, assignment_name), '%Y-%m-%d-%H-%M')
due_timestamp = due_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')

if len(sys.argv) == 2:
  print('Adding future lock override for ' + assignment_name)
  #set future locks
  groups = [group for group in get_groups(dsci100) if 'Loading Group' in group['name']]
  for group in groups:
    print('Group ' + str(group['name']))
    print('Unlocks at: ' + future_unlock_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'))
    users = get_group_users(dsci100, str(group['id']))
    user_ids = [user['id'] for user in users]
    print('num users = ' + str(len(user_ids)))
    lock_title = assignment_name + '_' + group['name'] + '_lock'
    set_assignment_dates(dsci100, str(assignment_id), user_ids, lock_title, future_unlock_timestamp, due_timestamp, lock_timestamp)
elif sys.argv[2] == 'show':
  print(get_assignment_overrides(dsci100, assignment_id))
else:
  group_num = sys.argv[2]
  print('Removing future lock override for ' + assignment_name + ', loading group ' + group_num)
  overrides = get_assignment_overrides(dsci100, assignment_id)
  for override in overrides:
    if 'Loading Group ' + group_num in override['title']:
      delete_override(dsci100, assignment_id, str(override['id']))




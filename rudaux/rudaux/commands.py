import os
import rudaux
import terminaltables as ttbl

def print_list(args):
    course = rudaux.Course(args.directory)
    printouts = {'students' : 'Students', 'groups' : 'Groups', 'instructors' : 'Instructors', 'tas' : 'Teaching Assistants', 'assignments' : 'Assignments'}
    none_selected = not any([vars(args)[po] for po in printouts])
    for po in printouts:
        if vars(args)[po] or none_selected:
            title = printouts[po]
            if len(course.__dict__[po]) > 0:
                tbl = [type(course.__dict__[po][0]).table_headings()]
                for obj in course.__dict__[po]:
                    tbl.append(obj.table_items())
            else:
                tbl = []
            print(ttbl.AsciiTable(tbl, title).table)

#def apply_latereg_extensions(args):
#    course = rudaux.Course(args.directory, dry_run = args.dry_run)
#    course.apply_latereg_extensions()
#
## this is the only command that gets called on the student hub (for now)
## it should be called every X minutes using a cron job (X = 15, say, if you want your snapshots to have a max resolution of 15 mins)
## snapshots will only happen once per assignment (and once per override), so even if you set X = 1, it'll just make this command run a bunch without
## actually doing anything. The only cost is that it has to run this code every minute, which is probably too much. Most assignments are due
## on the hour / half hour at most, so every 15 should almost always be fine.
#def snapshot(args):
#    course = rudaux.Course(args.directory, dry_run = args.dry_run)
#    # if course setup fails, do ???
#    # do a non-blocking update: 
#    # if update fails (e.g. canvas is down), just take snapshots based on previous course obj. Snapshots are cheap and we may as well be conservative
#    course.take_snapshots()
#  
#    #TODO snapshots run every 30m, too many emails. 
#    #see todo below about digest messages
#    #course.send_notifications()
#    
#
#def run(args):
#    course = rudaux.Course(args.directory, dry_run = args.dry_run)
#    # if course setup fails, do ???
#    # do a non-blocking update: 
#    # if update fails (e.g. canvas is down), just take snapshots based on previous course obj. Snapshots are cheap and we may as well be conservative
#    course.grading_workflow()
#
## TODO implement a send notification command
## and have smtp.submit save notifications to disk
## so that the user can control how often their messages are sent (digest)



#Ideas for other commands:
#status #return a report of status; subcommands:
##assignment (graded / feedback / solutions / etc)
##snapshot schedule 
##hard drive / memory usage? 
##errors in assignment grading
#
#schedule_tasks #creates a schedule of commands that run automatically
#               #snapshots, cloning repos, pulling, etc
#
#run #force running of a particular task now
#
##same commands as dictauth, just for rudaux_config
##these will call dictauth commands
#encrypt_password
#
#graders:
#list
#add
#remove



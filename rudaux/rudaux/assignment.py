class Assignment:

    #TODO -- this has state now, so we need to make sure not overwritten by synchronize
    def __init__(self, canvas_dict):
        self.__dict__.update(canvas_dict)
        self.snapshot_taken = False
        self.override_snapshots_taken = []
        self.grader_workloads = {}
        self.course_slug = config.course_slug

    def __repr__(self):
        return self.name + '(' + self.canvas_id + '): ' + ('jupyterhub' if self.is_jupyterhub_assignment else 'canvas') + ' assignment'

    @classmethod
    def table_headings(cls):
        return ['Name', 'Canvas ID', 'Due', 'Unlock', 'Lock']

    def table_items(self):
        #TODO pass in tz for non america/vancouver timezones
        return [self.name, self.canvas_id, self.due_at.in_timezone('America/Vancouver').format('ddd YYYY-MM-DD HH:mm:ss') if self.due_at else 'N/A',
                                           self.unlock_at.in_timezone('America/Vancouver').format('ddd YYYY-MM-DD HH:mm:ss') if self.unlock_at else 'N/A', 
                                           self.lock_at.in_timezone('America/Vancouver').format('ddd YYYY-MM-DD HH:mm:ss') if self.lock_at else 'N/A']

    #need this function to remove special characters (e.g. underscores) from jupyter user names on instructor server
    def grader_basename(self):
        return ''.join(ch for ch in self.name if ch.isalnum())+ '-' + self.course_slug + '-grader-'

    def get_due_date(self, s):
        basic_date = self.due_at

        #get overrides for the student
        overrides = [over for over in self.overrides if s.canvas_id in over['student_ids'] and (over['due_at'] is not None)]

        #if there was no override, return the basic date
        if len(overrides) == 0:
            return basic_date, None

        #if there was one, get the latest override date
        latest_override = overrides[0]
        for over in overrides:
            if over['due_at'] > latest_override['due_at']:
                latest_override = over
        
        #return the latest date between the basic and override dates
        if latest_override['due_at'] > basic_date:
            return latest_override['due_at'], latest_override
        else:
            return basic_date, None

        #self.all_submissions=[]
        #self.client = docker.from_env()
        #self.container = client.containers.get('45e6d2de7c54') #TODO what container?
        #self.is_manual_grading_required = False #TA grading required? 

        ##'unlock_at': '2020-05-12T06:00:00Z', #unlock date
        ##'lock_at': '2020-11-29T06:59:59Z', #lock date
        #self.is_unlocked = False  #before assignment is released - so that studet can click on the link
        #self.is_locked   = False  #after assignment is locked - no longer accepting submissions
        ##QUESTION: DIFFERENCE BETWEEN LOCKED & PASTDUE

        ##'due_at': '2020-10-01T05:59:59Z', #due date
        #self.is_past_due = False #after assignment due date

        ##'has_submitted_submissions'
        ##'in_closed_grading_period'
        #self.is_grading = False #grading ongoing
        #self.is_graded = False  #grading completed
        #self.is_grade_collected = False #gradebook merged
        #self.is_grade_posted = False #grades posted - assignment is done!

        ##
        #self.is_error = False # assignment of a submission of this assignment has an error
        #self.error_msg = []

        #TODO add list of graders/instructors (could be the same person, but not necessarily) (cwl)


    #def autograde(self):
    #    pass

    #def generate_assignment():
    #    return 0

    ## TODO build the all_submissions list
    #def collect_all_submissions(self):
    #    return 0

    ## TODO assign graders
    #def assign_graders(self):
    #    return 0

    ## TODO copy student files to graders
    #def copy_all_submissions(self):
    #    return 0

    #def autograde_assignments():
    #    return 0
    #def generate_feedback():
    #    return 0
    #def generate_solution():
    #    return 0
    #def return_feedback():
    #    return 0
    #def return_solution():
    #    return 0
    #def compute_max_score():
    #    return 0

    ##QUESTIONS
    #def backup_grades():
    #    return 0
    #def backup_gradebooks():
    #    return 0

    ##process ungraded assignments
    #def process_new_assignments():
    #    return 0

    ##DO functions to figure out combinations of different flag status
    #def set_is_unlocked(self):
    #    unlock_date    = parse_canvas_dates(assignment_info['unlock_at'])
    #    if datetime.datetime.today() > unlock_date:
    #        self.is_unlocked = True

    #def set_is_past_due(self):
    #    due_date    = parse_canvas_dates(assignment_info['is_past_due'])
    #    if datetime.datetime.today() > due_date:
    #        self.is_past_due = True

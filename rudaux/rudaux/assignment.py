class Assignment:

    def __init__(self, canvasdict):
        self.canvas_update(canvasdict)
        self.submissions = []
        self.snapshot_taken = False
        self.override_snapshots_taken = []

    def __repr__(self):
        return self.name + '(' + self.canvas_id + '): ' + ('jupyterhub' if self.is_jupyterhub_assignment else 'canvas') + ' assignment'

    @classmethod
    def table_headings(cls):
        return ['Name', 'Canvas ID']

    def table_items(self):
        return [self.name, self.canvas_id]

    def canvas_update(self, canvasdict):
        self.__dict__.update(canvasdict)
    
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

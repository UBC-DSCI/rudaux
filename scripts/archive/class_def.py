#student

#TODO course object for traitlet
#TODO course object for canvas access 


class Student:

    # Class Attributes ?
        #TODO
        #shared path goes here

        
    # Instance Attributes
    def __init__(self, stu_id, date):
        self.student_id = stu_id
        self.enrollment_date = date # member function
        #
        #TODO as a dictionary
        # read each student once
        # CACHE HTTPS REQUESTS!
        # read list of students multiple times.
        self.submissions = []
        #gradebook?


    # Getter Methods
    def get_submissions(self):
        #TODO
        return 0 

    # Setter Methods
    def add_submissions(self,new_submission):
        #TODO
        return 0

#assignment
class Assignment:
    # Class Attributes ?
        #TODO
        #shared path goes here
    
    # Instance Attributes
    def __init__(self, assgmt_id):
        self.assigment_id = assgmt_id


        self.due_date = 0  #assignment due date
        self.grader_id = 0 #TA/Instructor ID

        self.isManualGradingRequired = False #TA grading required? 
        self.isLocked = False  #before assignment is released
        self.isPastDue = False #after assignment due date
        self.isGrading = False #grading ongoing
        self.isGraded = False  #grading completed
        self.isGradeCollected = False #gradebook merged
        self.isGradePosted = False #grades posted - assignment is done!

    # Getter Methods
        # TODO
        def setIsGrading(self):
            #TODO
            return 0

    # Setter Methods
        # TODO
        def setGradeBook(self):
            #TODO
            return 0

class Submission:
    # Class Attributes ?
        #TODO
        #shared path goes here

    # Instance Attributes
    def __init__(self, stud, assgmt, sub_id):
        self.student = stud
        self.assigment = assgmt
        self.submission_id = sub_id
        # self.solution_file

        self.isCollected = False    #is the submission collected by the TA to their directory?
        self.isGraded = False       #is the submission graded?
        self.isGradePosted = False  #is grade posted?
        self.isLate = False         #is the submission late?

    # Getter Methods
      # TODO

    # Setter Methods
      # TODO

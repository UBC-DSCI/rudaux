class Assignment:

    #TODO -- this has state now, so we need to make sure not overwritten by synchronize
    def __init__(self, canvas_dict):
        self.__dict__.update(canvas_dict)
        self.snapshot_taken = False
        self.override_snapshots_taken = []
        self.grader_workloads = {}

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
        return ''.join(ch for ch in self.name if ch.isalnum())+'-grader-'

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

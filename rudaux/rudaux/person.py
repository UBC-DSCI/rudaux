class Person:

    def __init__(self, canvas_dict):
        self.__dict__.update(canvas_dict)
        self.submissions = []

    def __repr__(self):
        return self.name + ' (' + self.canvas_id  + ')'

    @classmethod
    def table_headings(cls):
        return ['Name', 'Canvas ID', 'SIS ID', 'RegCreated', 'RegUpdated', 'Status']

    def table_items(self):
        return [self.name, self.canvas_id, self.sis_id, self.reg_created.in_timezone('America/Vancouver').format('ddd YYYY-MM-DD HH:mm:ss'), self.reg_updated.in_timezone('America/Vancouver').format('ddd YYYY-MM-DD HH:mm:ss'), self.status]

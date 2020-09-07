class Person:

    def __init__(self, canvas_dict):
        self.__dict__.update(canvas_dict)
        self.submissions = []

    def __repr__(self):
        return self.name + ' (' + self.canvas_id  + ')'

    @classmethod
    def table_headings(cls):
        return ['Name', 'Canvas ID']

    def table_items(self):
        return [self.name, self.canvas_id]

    def canvas_update(self, canvasdict):
        self.__dict__.update(canvasdict)

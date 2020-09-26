class Group:

    def __init__(self, canvas_dict):
        self.__dict__.update(canvas_dict)

    def __repr__(self):
        return self.name + ' (' + self.canvas_id  + '), members: ' + str(self.members)

    @classmethod
    def table_headings(cls):
        return ['Name', 'Canvas ID', 'Members']

    def table_items(self):
        return [self.name, self.canvas_id, str(self.members)]

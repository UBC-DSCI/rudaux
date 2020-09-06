class Person:

    def __init__(self, canvasdict):
        self.__dict__.update(canvasdict)
        self.submissions = []

    def __repr__(self):
        return self.name + ' (' + self.canvas_id  + ')'

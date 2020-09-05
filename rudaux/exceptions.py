

class CanvasError(Exception):
    def __init__(self, caller, url, resp):
        self.caller = caller
        self.url = url
        self.resp = resp

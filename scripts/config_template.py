from traitlets.config.application import get_config

c = get_config()
c.Course.canvas_domain = 'https://canvas.ubc.ca'
c.Course.course_id = 12345678
c.Course.course_token = 'token'

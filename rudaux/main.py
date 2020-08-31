if __name__ == '__main__':
    from Course import Course
    from traitlets.config import PyFileConfigLoader


    #import course configurations
    # TODO see test.py
    cfg_loader = PyFileConfigLoader("config.py")
    cfg = cfg_loader.load_config()
    dsci100 = Course(config=cfg)

    #create new students
    # TODO: read students from canvas
    reply = Course.get_all_students(dsci100)
    #print(reply)
    parsed_reply = Course.parse_canvas_response(dsci100,reply)
    #print(parsed_reply)
    students = Course.create_all_students(dsci100,parsed_reply)
    # TODO: create a list of students


    reply = Course.get_all_assignments(dsci100)
    parsed_reply = Course.parse_canvas_response(dsci100,reply)
    assignments = Course.create_all_assignments(dsci100,parsed_reply)
    #grading
    # run 2 times a week for all assignments
    # TODO: if (past due && not graded)
    #           if && requires manual grading, then assign to a TA 
    #           else assign to an instructor
    # TODO: use subprocess to pull instructuor repo so that graders don't have to do it themselves.
    # Actual grading is done on Formgrader & JupyterHub

    #collect grades
    # run 2 times a week for all assignments
    # TODO: if (past due & graded & grades not collected)
    #           collect gradebooks from TA

    #posting grades
    # run 2 times a week for all assignments
    # TODO: if (graded & grades collected & grades not posted)
    #           post grades


import prefect

def get_logger():
    return prefect.context.get("logger")

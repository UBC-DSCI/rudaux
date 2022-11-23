# ----------------------------------------------------------------------------------------------------------
def clean_jhub_uname(s):
    return ''.join(ch for ch in s if ch.isalnum())


# ----------------------------------------------------------------------------------------------------------
def grader_account_name(group_name: str, assignment_name: str, username: str):
    return clean_jhub_uname(group_name) + clean_jhub_uname(assignment_name) + clean_jhub_uname(username)

# ----------------------------------------------------------------------------------------------------------

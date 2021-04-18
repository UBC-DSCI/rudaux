from prefect import Flow, unmapped, flatten, task

@task
def get_pairs(list1, list2):
    return [(a, b) for a in list1 for b in list2]


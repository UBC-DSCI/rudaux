import numpy as np
import pandas as pd
import pendulum as plm
import os
import humanfriendly as hf
import io
import re

def get_user(info):
    if "name=jupyter" in info:
        matches = re.findall(r"name=jupyter-\d+", info)
        if len(matches) != 1:
            print(f"ERROR: re did not find one username: {matches}")
        return matches[0][13:]
    else:
        return ""

def get_date_time(tstmp):
    dt = plm.parse(tstmp)
    return pd.Series({"year": dt.year, "month": dt.month, "day": dt.day, "hour": dt.hour, "minute" : dt.minute, "second": dt.second})

dfs = []
logfiles = sorted(os.listdir("docker-events"))
itr = 0
for lf in logfiles:
    fn = os.path.join("docker-events", lf)
    if "rebooted" in fn:
        # don't handle rebooted files yet...visualize data first and manually fix where needed
        continue
    print(f"Filling docker_events_{itr:03}.csv -- Processing {fn}")
    # read with whitespace delim; replace parentheses with " so pandas can read quoted entries
    with open(fn, "r") as f:
        fo = io.StringIO()
        data = f.readlines()
        if len(data) == 0:
            print(f"No data found in {fn}; skipping")
            continue
        fo.writelines(line.replace('(', '"'
                         ).replace(')', '"'
                         ).replace("health_status: healthy", "health_healthy"
		 	 ).replace("health_status: unhealthy", "health_unhealthy"
                         ).replace("exec_create: bash", "exec_create"
                         ).replace("exec_create: /bin/bash", "exec_create"
                         ).replace("exec_start: bash", "exec_start"
                         ).replace("exec_start: /bin/bash", "exec_start"
                         ).replace("exec_create: sh -c cp -a /tmp/user-settings/. /home/jupyter/.jupyter/lab/user-settings", "exec_create"
                         ).replace("exec_start: sh -c cp -a /tmp/user-settings/. /home/jupyter/.jupyter/lab/user-settings", "exec_start"
			 ).replace("exec_create: /bin/sh -c wget -O- --no-verbose --tries=1 --no-check-certificate     http${GEN_CERT:+s}://localhost:8888${JUPYTERHUB_SERVICE_PREFIX:-/}api || exit 1", "exec_create"
			 ).replace("exec_start: /bin/sh -c wget -O- --no-verbose --tries=1 --no-check-certificate     http${GEN_CERT:+s}://localhost:8888${JUPYTERHUB_SERVICE_PREFIX:-/}api || exit 1", "exec_create"
            ) for line in data)
        fo.seek(0)

    df_tmp = pd.read_table(fo, sep='\s+', header=None)

    # rename columns
    df_tmp.columns = ['timestamp', 'type', 'action', 'container', 'info']

    # extract user from info coln
    df_tmp["user"] = df_tmp["info"].apply(get_user)

    # process timestamp
    df_tmp = df_tmp.merge(df_tmp["timestamp"].apply(get_date_time), left_index=True, right_index=True)

    # shorten container (docker stats uses 6 bytes, so keep 6 bytes here too instead of 32)
    df_tmp["container"] = df_tmp["container"].str[:12]

    # remove unused columns
    df_tmp = df_tmp[["year", "month", "day", "hour", "minute", "second", "user", "type", "action", "container"]]

    # append to the list of dataframes
    dfs.append(df_tmp)

    if len(dfs) == 7:
        df = pd.concat(dfs)
        df.to_csv(f"processed/docker_events_{itr:03}.csv", index=False)
        itr += 1
        dfs = []

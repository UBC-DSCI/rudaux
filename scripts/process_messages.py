import numpy as np
import pandas as pd
import pendulum as plm
import os
import humanfriendly as hf
import io
import re

logfiles = os.listdir("messages")
itr = 0
for lf in logfiles:
    fn = os.path.join("messages", lf)

    print(f"Filling messages_{itr:03}.csv -- Processing {fn}")
    # read with whitespace delim; standardize columns / whitespace with "
    with open(fn, "r") as f:
        fo = io.StringIO()
        data = f.readlines()

        # find where the message is and surround with quotes
        data2 = []
        for line in data:
            tokens = line.replace('"', '').split()

            # filter lines to keep only messages with info
            tokens[4] = tokens[4][:-1] # rm : after jupyterhub
            if tokens[4] != 'jupyterhub': continue
            if tokens[5][0] != '[': continue # ignore messages that don't have [xxx] structure
            if len(tokens) != 15: continue # only desired messages; this ignores "Checking routes" and "removed from proxy" messages
            if tokens[9] != 'log:174]': continue # messages with activity data from students

            # clean up the lines
            tokens[5] = tokens[5][1:]  # rm [ before I,W, or E
            tokens[9] = tokens[9][:-1] # rm ] after message
            tokens[13] = tokens[13][1:-1] # rm ( before and ) after line
            tokens[14] = tokens[14][:-2] # rm 'ms' after number

            # join but separate user number from ip address in tokens[13]
            data2.append(" ".join(tokens) + '\n' )
        # end for

        if len(data2) == 0:
            print(f"No data found in {fn}; skipping")
            continue
        # end if

        fo.writelines(data2)
        fo.seek(0)
    # end with

    # read the table and rename the columns
    df_tmp = pd.read_table(fo, delim_whitespace=True, header=None)

    df_tmp.columns = ["month", "day", "timestamp", "host", "service", "msg_type", "date", "timestamp2", "service2", "origin", "request_no", "request_type", "directory", "user_IP", "time"]

    # get times
    df_tmp[["hour", "minute", "second"]] = df_tmp["timestamp"].str.strip("[").str.strip("]").str.split(":", expand=True)

    # get date
    df_tmp["year"] = lf[9:13]
    df_tmp["month"] = df_tmp["month"].map({"Jan" : 1, "Feb" : 2, "Mar" : 3, "Apr" : 4, "May" : 5, "Jun" : 6, "Jul" : 7, "Aug" : 8, "Sep" : 9, "Oct" : 10, "Nov" : 11, "Dec" : 12})

    # remove unused columns
    df_tmp = df_tmp[["year", "month", "day", "hour", "minute", "second", "service", "msg_type", "origin", "request_no", "request_type", "directory", "user_IP"]]

    # output to file
    df_tmp.to_csv(f"processed/jh_messages_{itr:03}.csv", index=False)
    itr += 1
# end for
print('Done!')

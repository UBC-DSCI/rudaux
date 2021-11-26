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
            assert tokens[4][-1] == ":", f"didnt work {tokens}"
            tokens[4] = tokens[4][:-1]
            data2.append( " ".join(tokens[:5]) + ' "' + " ".join(tokens[5:]) + '"\n' )

        if len(data2) == 0:
            print(f"No data found in {fn}; skipping")
            continue
 
        fo.writelines(data2)
        fo.seek(0)

    # read the table and rename the columns
    df_tmp = pd.read_table(fo, delim_whitespace=True, header=None)

    df_tmp.columns = ["month", "day", "timestamp", "host", "service", "info"]

    # get times
    df_tmp[["hour", "minute", "second"]] = df_tmp["timestamp"].str.strip("[").str.strip("]").str.split(":", expand=True)

    # get date
    df_tmp["year"] = lf[9:13]
    df_tmp["month"] = df_tmp["month"].map({"Jan" : 1, "Feb" : 2, "Mar" : 3, "Apr" : 4, "May" : 5, "Jun" : 6, "Jul" : 7, "Aug" : 8, "Sep" : 9, "Oct" : 10, "Nov" : 11, "Dec" : 12})

    # remove unused columns
    df_tmp = df_tmp[["year", "month", "day", "hour", "minute", "second", "service", "info"]]

    # output to file
    df_tmp.to_csv(f"processed/messages_{itr:03}.csv", index=False)
    itr += 1

import numpy as np
import pandas as pd
import pendulum as plm
import os
import humanfriendly as hf
import io
import re
import functools

logfiles = os.listdir("sar")
itr = 0
file_itr = 0
datadict = {}
for lf in logfiles:
    fn = os.path.join("sar", lf)

    print(f"Filling sar_{file_itr:03}.csv -- Processing {fn}")

    # look for whitespace lines
    # the next line is column names (and a timestamp)
    # if the colnames already exist, just keep appending
    # if the colnames dont exist, add them

    with open(fn, "r") as f:
        data = f.readlines()

    # date from filename
    year = lf[4:8]
    month = lf[9:11]
    day = lf[12:14]

    # remove the two header lines
    data = data[2:]

    # if the file is empty, skip it
    if len(data) == 0:
        continue

    # ignore lines that contain Average or RESTART and process time AM/PM to 24h
    # add year, month, day data
    data2 = []
    data2.append("year month day hour minute second " + " ".join(data[0].split()[2:]) + "\n")
    for i in range(1, len(data)):
        if 'RESTART' in data[i] or 'Average' in data[i]:
            continue
        toks = data[i].split()
        if len(toks) > 0:
            tt = [int(t) for t in toks[0].split(':')]
            if toks[1] == 'PM' and tt[0] != 12:
                tt[0] += 12
            if toks[1] == 'AM' and tt[0] == 12:
                tt[0] = 0
            if len(data2[-1].strip()) == 0:
                # this is a header line
                data2.append(f"year month day hour minute second " + " ".join(toks[2:]) + "\n")
            else:
                data2.append(f"{year} {month} {day} {tt[0]:02} {tt[1]:02} {tt[2]:02} " + " ".join(toks[2:]) + "\n")
        else:
            # this line is empty, only add the line if the previous one wasn't empty (no need for multiple empty in a row)
            if len(data2[-1].split()) > 0:
                data2.append(data[i])

    # now different dataframes are split by a single empty line
    # create sublists for each header, and go line by line through data2 and use the headers to switch state
    # and append lines to the correct subheader
    # basically we need to do this because restarts break up the same dataframe into multiple chunks
    # and also CPU, IFACE, etc sometimes are too long and get chunked by sar

    if data2[0] not in datadict:
        datadict[data2[0]] = [data2[0]]
    curheader = data2[0]
    for i in range(1, len(data2)):
        if len(data2[i].strip()) == 0:
            continue
        if len(data2[i-1].strip()) == 0:
            # update the header
            curheader = data2[i]
            continue
        if curheader not in datadict:
            datadict[curheader] = [curheader]
        datadict[curheader].append(data2[i])

    if (itr+1) % 7 == 0:
        none_dfs = []
        for header, data in datadict.items(): 
            fo = io.StringIO()
            fo.writelines(data)
            fo.seek(0)
            # read the table and rename the columns
            df = pd.read_table(fo, delim_whitespace=True)
            prefix = ""
            if "CPU" in header:
                prefix = "sar_cpu"
            elif "TTY" in header:
                prefix = "sar_tty"
            elif "DEV" in header:
                prefix = "sar_dev"
            elif "IFACE" in header and "rxpck" in header:
                prefix = "sar_iface_pck"
            elif "IFACE" in header and "rxerr" in header:
                prefix = "sar_iface_err"
            else:
                none_dfs.append(df)
                continue
            df.to_csv(f"processed/{prefix}_{file_itr:03}.csv", index=False)
        none_df = functools.reduce(lambda x, y : pd.merge(x, y, how='inner'), none_dfs)
        none_df.to_csv(f"processed/sar_none_{file_itr:03}.csv", index=False)
        datadict = {}
        file_itr += 1
    itr += 1





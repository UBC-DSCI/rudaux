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
logfiles = os.listdir("docker-stats")
itr = 0
for lf in logfiles:
    fn = os.path.join("docker-stats", lf)

    print(f"Filling docker_stats_{itr:03}.csv -- Processing {fn}")
    # read with whitespace delim; standardize columns / whitespace with "
    with open(fn, "r") as f:
        fo = io.StringIO()
        data = f.readlines()
        
        # clean up the lines a bit
        data2 = [line.replace(" / ", " ").replace("1e+03", "1000") for line in data if "--" not in line]
        # a common error in the stat files is that you get a timestamp for one line, then the full next line, then the remainder of the first; so fix that here
        # fix: anywhere there are duplicated timestamps, just keep the first and copy that timestamp to subsequent lines
        data3 = []
        for i in range(len(data2)):
            line = data2[i]
            if line.count("[") > 1:
                line = line[line.rfind("["):]
            if line.count("[") == 0:
                prevline = data3[i-1]
                prevstamp = prevline[:prevline.rfind("]")+1]
                line = prevstamp + " " + line
            data3.append(line)

        # finally remove header rows
        data4 = [line for line in data3 if 'CONTAINER' not in line]

        if len(data4) == 0:
            print(f"No data found in {fn}; skipping")
            continue
 
        fo.writelines(data4)
        fo.seek(0)

    # read the table and rename the columns
    df_tmp = pd.read_table(fo, delim_whitespace=True, header=None)

    df_tmp.columns = ["timestamp", "container", "name", "cpu_pct", "mem_usage", "mem_limit", "mem_pct", "net_in", "net_out", "block_in", "block_out", "pids"]

    # get user column
    df_tmp["user"] = df_tmp["name"].str[8:]

    # get times
    df_tmp[["hour", "minute", "second"]] = df_tmp["timestamp"].str.strip("[").str.strip("]").str.split(":", expand=True)

    # get date from filename
    df_tmp["year"] = lf[6:10]
    df_tmp["month"] = lf[11:13]
    df_tmp["day"] = lf[14:16]

    # remove % sign from cpu_pct
    df_tmp["cpu_pct"] = df_tmp["cpu_pct"].str.replace("%", "")

    # make sizes human friendly
    df_tmp["mem_usage_mb"] = df_tmp["mem_usage"].apply(hf.parse_size)/1000000
    df_tmp["mem_limit_mb"] = df_tmp["mem_limit"].apply(hf.parse_size)/1000000
    df_tmp["net_in_mb"] = df_tmp["net_in"].apply(hf.parse_size)/1000000
    df_tmp["net_out_mb"] = df_tmp["net_out"].apply(hf.parse_size)/1000000
    df_tmp["block_in_mb"] = df_tmp["block_in"].apply(hf.parse_size)/1000000
    df_tmp["block_out_mb"] = df_tmp["block_out"].apply(hf.parse_size)/1000000

    # remove unused columns
    df_tmp = df_tmp[["year", "month", "day", "hour", "minute", "second", "user", "container", "cpu_pct", "mem_usage_mb", "mem_limit_mb", "net_in_mb", "net_out_mb", "block_in_mb", "block_out_mb", "pids"]]

    # append to the list of dataframes
    dfs.append(df_tmp)

    if len(dfs) == 7:
        df = pd.concat(dfs)
        df.to_csv(f"processed/docker_stats_{itr:03}.csv", index=False)
        itr += 1
        dfs = []

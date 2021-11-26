import numpy as np
import pandas as pd
import pendulum as plm
import os
import humanfriendly as hf


dfs = []
logfiles = os.listdir("hdusage")
itr = 0
for lf in logfiles:
    fn = os.path.join("hdusage", lf)
    print(f"Filling hd_{itr:03}.csv -- Processing {fn}")
    # read with whitespace delim
    df_tmp = pd.read_table(fn, delim_whitespace=True)
    # remove empty "on" column, rename first to timestamp
    df_tmp = df_tmp.drop(columns = 'on').rename(columns = {df_tmp.columns[0] : "timestamp"})
    # filter rows to only those for jhub user folders
    df_tmp = df_tmp[ df_tmp["Filesystem"].str.contains("tank/home/dsci100/") & ~df_tmp["Filesystem"].str.contains("@") ]
    # extract the date from the filename
    df_tmp["year"] = lf[6:10]
    df_tmp["month"] = lf[11:13]
    df_tmp["day"] = lf[14:16]
    # extract the time from the timestamp
    df_tmp[["hour", "minute", "second"]] = df_tmp["timestamp"].str.strip("[").str.strip("]").str.split(":", expand=True)
    # extract user number from filesystem
    df_tmp["user"] = df_tmp["Filesystem"].str.split("/").str[-1]
    # extract numerical bytes from human-friendly sizes
    df_tmp["size_mb"] = df_tmp["Size"].apply(hf.parse_size)/1000000
    df_tmp["used_mb"] = df_tmp["Used"].apply(hf.parse_size)/1000000
    # remove unused columns
    df_tmp = df_tmp[["year", "month", "day", "hour", "minute", "second", "user", "size_mb", "used_mb"]]
    # append to the list of dataframes
    dfs.append(df_tmp)

    if len(dfs) == 7:
        df = pd.concat(dfs)
        df.to_csv(f"processed/hd_{itr:03}.csv", index=False)
        itr += 1
        dfs = []

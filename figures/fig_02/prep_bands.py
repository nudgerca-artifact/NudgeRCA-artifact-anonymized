"""Cache the existing rule's per-window statistics for the two Tomcat01 signals.

Output: data/band_tables.json
  {kpi_short: {bin: [mean, sd, max, min]}}  where bin = unix_ts // 600 (10-min window),
  mean/std are from the 5 min immediately before the window (v4 baseline),
  sd = max(std, |mean| * 1%, KPI scale * 1%, 1e-6)  (v4 sigma floor),
  max/min are the values inside the window.
Also writes data/tomcat01_memory_kpis.txt: Tomcat01 memory-related KPIs on the first day (unit hint).
"""
import os, json, numpy as np, pandas as pd
ROOT=os.path.join(os.environ.get("RCA_DATASETS", "datasets"), "OpenRCA", "Bank", "telemetry")
HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(os.path.dirname(HERE),"data")
KJ="Tomcat-MEMORY_7441-MEMORY_JVMUsedMemory"; KC="OSLinux-OSLinux_MEMORY_MEMORY_CacheMem"
parts=[]; hint=None
for d in sorted(os.listdir(ROOT)):
    f=f"{ROOT}/{d}/metric/metric_container.csv"
    if not os.path.exists(f): continue
    df=pd.read_csv(f,usecols=["timestamp","cmdb_id","kpi_name","value"],low_memory=False)
    if hint is None:
        t=df[(df.cmdb_id.astype(str)=="Tomcat01")&df.kpi_name.str.contains("MEMORY|Mem",regex=True)]
        hint=t.groupby("kpi_name").value.agg(["median","min","max","count"]).to_string()
        open(os.path.join(DATA,"tomcat01_memory_kpis.txt"),"w").write(f"# {d}\n{hint}\n")
    df=df[df.kpi_name.isin([KJ,KC])]; ts=df["timestamp"]; df["timestamp"]=(ts/1000 if ts.median()>1e11 else ts).astype(int); parts.append(df)
    print("read",d,len(df),flush=True)
M=pd.concat(parts); M["value"]=pd.to_numeric(M["value"],errors="coerce"); M=M.dropna(); M["cmdb_id"]=M.cmdb_id.astype(str)
M["bin"]=M.timestamp//600; M["half"]=(M.timestamp%600)>=300; M["a"]=M.value.abs()
sw=M.groupby(["kpi_name","bin"])["a"].max(); sb=M[M.half].assign(bin=M.bin[M.half]+1).groupby(["kpi_name","bin"])["a"].max(); scale=pd.concat([sw,sb],axis=1).max(axis=1)
out={}
for short,k in [("jvm",KJ),("cache",KC)]:
    g=M[(M.cmdb_id=="Tomcat01")&(M.kpi_name==k)]; w=g.groupby("bin").value.agg(["max","min"]); b=g[g.half].groupby("bin").value.agg(["mean","std"]); b.index=b.index+1; j=w.join(b,how="inner")
    fl=0.01*scale.xs(k).reindex(j.index).fillna(0).values; sd=np.maximum.reduce([j["std"].fillna(0).values,np.abs(j["mean"].values)*0.01,fl,np.full(len(j),1e-6)])
    out[short]={int(i):[float(r["mean"]),float(s),float(r["max"]),float(r["min"])] for (i,r),s in zip(j.iterrows(),sd)}
    print(short,"windows with baseline:",len(out[short]))
json.dump(out,open(os.path.join(DATA,"band_tables.json"),"w")); print("saved data/band_tables.json")

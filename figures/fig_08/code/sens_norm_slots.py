"""Fault-free log-template and trace-latency records in 5-minute slots (ts // 300) for the sensitivity runs. Uses the template normalization,
fault windows (+-300 s) and unit conversion of the original builders (build_bank_spec_norm.py, build_market_ch_norm.py), so that slot // 2 (one
10-minute window) reproduces their normal profiles (n_windows, windows per template, mean latency per service). Output: output/sens/<ds>_slots.pkl"""
import json, glob, os, re, sys, collections, pickle
from multiprocessing import Pool
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.normpath(os.path.join(HERE, "..", "..", "baseline-cache"))
DS = sys.argv[1]; RAWD = os.environ.get("RCA_DATASETS", "datasets"); S = 300
if DS == "bank":
    RAW = f"{RAWD}/OpenRCA/Bank/telemetry"; CAT = set(json.load(open(f"{HERE}/output/component_catalog_bank.json")))
    UNK = set(json.load(open(os.environ["UNKNOWN_IDS"]))) if os.environ.get("UNKNOWN_IDS") else set()
    W = sorted((c["win_start"] - 300, c["win_end"] + 300) for c in (json.load(open(f)) for f in glob.glob(f"{HERE}/output/cases_query_bank/*.json")) if c["case_id"] not in UNK)
else:
    RAW = f"{RAWD}/OpenRCA/Market/cloudbed-{DS[-1]}/telemetry"; CAT = None
    UNK = set(json.load(open(os.environ["UNKNOWN_IDS"]))) if os.environ.get("UNKNOWN_IDS") else set()
    W = sorted((t["win_start"] - 300, t["win_end"] + 300) for t in (json.loads(l) for l in open(f"{B}/datasets/{DS}/query_tasks_{DS}.jsonl")) if t["win_start"] and t["case_id"] not in UNK)
ES = np.array([s for s, _ in W]); EE = np.array([e for _, e in W]); POD = re.compile(r"-\d+$")
UNKF = os.environ.get("UNKNOWN_IDS")   # json list of case ids whose windows are not excluded (evaluation incidents); output <ds>_slots_tk.pkl
NOEX = os.environ.get("NOEXCL") == "1"   # label-free profile: no window excluded, output <ds>_slots_noex.pkl
def is_fault(ts):
    if NOEX: return np.zeros(len(ts), bool)
    i = np.clip(np.searchsorted(ES, ts, side="right") - 1, 0, len(W) - 1); return (ts >= ES[i]) & (ts <= EE[i])
def norm_msg(sr):
    sr = sr.astype(str).str.slice(0, 300) if DS != "bank" else sr.str.slice(0, 300)
    sr = sr.str.replace(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", "<ts>", regex=True)
    sr = sr.str.replace(r"[0-9a-fA-F]{16,}", "<id>", regex=True).str.replace(r"[0-9a-fA-F-]{8,}", "<id>", regex=True)
    sr = sr.str.replace(r"\d+\.\d+", "<n>", regex=True).str.replace(r"\d+", "<n>", regex=True)
    return sr.str.slice(0, 140)
def do_log(f):
    tm = collections.defaultdict(set); sl = set()
    if DS == "bank":
        try: it = [pd.read_csv(f, usecols=["timestamp", "cmdb_id", "log_name", "value"], low_memory=False)]
        except Exception as ex: print("log file skipped", f, ex, flush=True); return tm, sl
    else: it = pd.read_csv(f, usecols=["timestamp", "cmdb_id", "value"], chunksize=1_000_000)
    for df in it:
        ts = pd.to_numeric(df["timestamp"], errors="coerce"); m = ts.notna().values; df = df.loc[m]; ts = ts[m].astype(np.int64).values
        if DS == "bank":
            ent = df["cmdb_id"].astype(str).values; msg = norm_msg(df["log_name"].astype(str) + ": " + df["value"].astype(str))
            key = pd.Series(ent, dtype="object").str.cat(pd.Series(msg.values, dtype="object"), sep="||").values
            keep = np.isin(ent, list(CAT)); ts, key = ts[keep], key[keep]
        else:
            svc = df["cmdb_id"].astype(str).str.replace(POD, "", regex=True); key = svc.values + "||" + norm_msg(df["value"]).values
        nm = ~is_fault(ts); s_ = ts[nm] // S; sl.update(np.unique(s_).tolist())
        for k, v in pd.DataFrame({"k": key[nm], "s": s_}).drop_duplicates().itertuples(index=False): tm[k].add(int(v))
    print("log done", f, flush=True); return tm, sl
def do_trace(f):
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))
    for ch in pd.read_csv(f, usecols=["timestamp", "cmdb_id", "duration"], chunksize=2_000_000, low_memory=False):
        ts = pd.to_numeric(ch["timestamp"], errors="coerce"); du = pd.to_numeric(ch["duration"], errors="coerce"); m = (ts.notna() & du.notna()).values
        tv = ts[m].astype(np.int64).values
        if DS == "bank":
            ts = np.where(tv > 10**12, tv // 1000, tv); du = du[m].astype(float).values; ent = ch.loc[m, "cmdb_id"].astype(str).values
            keep = np.isin(ent, list(CAT)); ts, du, ent = ts[keep], du[keep], ent[keep]
        else:
            ts = tv // 1000; du = du[m].astype(float).values / 1000.0; ent = ch["cmdb_id"].astype(str).str.replace(POD, "", regex=True)[m].values
        nm = ~is_fault(ts)
        if nm.any():
            g = pd.DataFrame({"e": ent[nm], "s": ts[nm] // S, "d": du[nm]}).groupby(["e", "s"])["d"].agg(["count", "sum"])
            for (e_, s_), r in g.iterrows(): a = acc[e_][int(s_)]; a[0] += int(r["count"]); a[1] += float(r["sum"])
    print("trace done", f, flush=True); return {e: dict(v) for e, v in acc.items()}
if __name__ == "__main__":
    if DS == "bank": lf = sorted(glob.glob(f"{RAW}/2*/log/*.csv")); tf = sorted(glob.glob(f"{RAW}/2*/trace/*.csv"))
    else: lf = sorted(glob.glob(f"{RAW}/*/log/log_*.csv")); tf = sorted(glob.glob(f"{RAW}/*/trace/trace_span.csv"))
    with Pool(len(lf) + len(tf)) as p:
        L = p.map_async(do_log, lf); T = p.map_async(do_trace, tf); L = L.get(); T = T.get()
    tm = collections.defaultdict(set); sl = set()
    for a, b in L:
        sl |= b
        for k, v in a.items(): tm[k] |= v
    tr = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0]))
    for d in T:
        for e, v in d.items():
            for s_, (n, sm) in v.items(): x = tr[e][s_]; x[0] += n; x[1] += sm
    out = {"log_slots": np.array(sorted(sl), dtype=np.int64), "tmpl": {k: np.array(sorted(v), dtype=np.int64) for k, v in tm.items()},
           "tr": {e: (np.array(sorted(v)), np.array([v[s][0] for s in sorted(v)]), np.array([v[s][1] for s in sorted(v)])) for e, v in tr.items()}}
    pickle.dump(out, open(f"{HERE}/output/sens/{DS}_slots{'_noex' if NOEX else ('_tk' if UNKF else '')}.pkl", "wb"))
    # check: 10-minute windows reproduce the builder's normalization
    nw = len(np.unique(out["log_slots"] // 2)); print(f"[{DS}] log normal 10-min windows {nw} | templates {len(tm)} | trace services {len(tr)}", flush=True)

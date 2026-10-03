"""Per-incident log and trace profiles for the profiling-period sweep: for each incident, the log-template EOB (windows in which the template
appears / windows with logs) and the per-service trace baseline latency (their mean) are recounted from only the fault-free windows used for its
metric profile (profile_windows of the case file), from the 5-minute slot records of sens_norm_slots.py (slot // 2 = one 10-minute window).
Bank keeps every service, Market only services with at least 1,000 normal spans, as in the original rule; only templates that occur in the
incident's window are written. Output: output/sens/casenorms_bank_<tag>.json, output/sens/casenorms_<tag>_market{1,2}.json"""
import json, os, sys, pickle, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); O = f"{HERE}/output/sens"; SYS, TAGS = sys.argv[1], sys.argv[2:]
def norms(X, keys, pw, min_spans):
    W = np.array(sorted(pw), dtype=np.int64); ls = np.unique(X["log_slots"] // 2); nw = int(np.isin(ls, W).sum())
    tmpl = {}
    for k in keys:
        s = X["tmpl"].get(k)
        if s is not None:
            c = int(np.isin(np.unique(s // 2), W).sum())
            if c: tmpl[k] = c
    tr = {}
    for e, (sl, n, sm) in X["tr"].items():
        m = np.isin(np.asarray(sl) // 2, W); nn = int(np.asarray(n)[m].sum())
        if nn and nn >= min_spans: tr[e] = float(np.asarray(sm)[m].sum() / nn)
    return {"n_windows": nw, "tmpl": tmpl, "trace": tr}
if SYS == "bank":
    X = pickle.load(open(f"{O}/bank_slots.pkl", "rb")); CB = json.load(open(f"{HERE}/output/bank_case_blocks.json"))
    for tag in TAGS:
        out = {}
        for f in sorted(glob.glob(f"{HERE}/output/cases_query_bank_L{tag}/*.json")):
            c = json.load(open(f)); pw = c.get("profile_windows")
            if pw: out[c["case_id"]] = norms(X, list((CB.get(c["case_id"], {}).get("log") or {}).keys()), pw, 1)
        json.dump(out, open(f"{O}/casenorms_bank_{tag}.json", "w")); print("bank", tag, len(out), "incidents", flush=True)
else:
    for ds in ("market1", "market2"):
        X = pickle.load(open(f"{O}/{ds}_slots.pkl", "rb")); CL = json.load(open(f"{HERE}/output/market_ch/{ds}_case_logtop.json"))
        for tag in TAGS:
            out = {}
            for f in sorted(glob.glob(f"{HERE}/output/cases_query_{ds}_full_L{tag}/*.json")):
                c = json.load(open(f)); pw = c.get("profile_windows")
                if pw: out[c["case_id"]] = norms(X, [k for k, _ in (CL.get(c["case_id"]) or [])], pw, 1000)
            json.dump(out, open(f"{O}/casenorms_{tag}_{ds}.json", "w")); print(ds, tag, len(out), "incidents", flush=True)

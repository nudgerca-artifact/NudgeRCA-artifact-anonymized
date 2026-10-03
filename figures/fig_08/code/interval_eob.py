"""Bank and Telecom cases for the profiling-period sweep. For each diagnosis window [s, e], mu and sigma of each (entity, KPI) (sigma =
max(sd, 1 %|mu|, 1e-6), at least --minn samples) and the EOB (share of the chosen fault-free windows in which max|v - mu| / sigma >= 3) are
recomputed from only the chosen fault-free windows (other incident windows +-300 s excluded, gaps skipped): "<N>:tag" the N windows before the
window, "nearN", "fracD" (round(all / D)) and "pctP" (P percent) the windows closest to it on both sides, and "all" the entire fault-free period
(at least 30 samples), which reproduces the paper's input. The diagnosis z and the candidate order (EOB ascending, z_max descending) use the same
statistics. Fault-free windows are 10 minutes long. Output: output/cases_query_<ds>_L<tag>/.
Usage: RCA_DATASETS=<raw> python3 interval_eob.py --dataset bank --H all:Hall pct90:HP90 frac2:HD2 ... [--only ids.json]"""
import json, os, sys, glob, argparse, importlib.util, collections
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); W = 600; K = 3.0   # 10-minute fault-free windows (s)
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", choices=["bank", "telecom", "market"], required=True)
ap.add_argument("--H", nargs="+", required=True); ap.add_argument("--only", default=None); ap.add_argument("--minn", type=int, default=10)
ap.add_argument("--unknown-ids", default=None, help="json list of case ids whose windows are NOT excluded (the evaluation incidents, unknown at diagnosis); only the other incidents (training split) are excluded")
ap.add_argument("--noexcl", action="store_true", help="label-free profile: no incident window is excluded, every sample and 10-minute window of the period is treated as normal")
a = ap.parse_args()
only = set(json.load(open(a.only))) if a.only else None
HS = [(h.split(":")[0], h.split(":")[1]) for h in a.H]

def build(name, load_day, days, tasks, catalog, profile_fn, orig_dir, out_prefix, excl=None):
    frames = []
    for d in days:
        df = load_day(d)
        if df is None or not len(df): continue
        frames.append(df[["timestamp", "entity", "kpi", "value"]])
    M = pd.concat(frames, ignore_index=True).dropna(subset=["timestamp", "value"])
    M["timestamp"] = M["timestamp"].astype(np.int64); M = M.sort_values("timestamp", kind="stable").reset_index(drop=True)
    code, uniq = pd.factorize(M["entity"].astype(str) + "||" + M["kpi"].astype(str))
    ts = M["timestamp"].values; val = M["value"].values.astype(float); nk = len(uniq); win = ts // W
    iv = excl if excl is not None else np.array(sorted((t["win_start"] - 300, t["win_end"] + 300) for t in tasks if t["win_start"] is not None))
    i = np.clip(np.searchsorted(iv[:, 0], ts, side="right") - 1, 0, len(iv) - 1); ff = ~((ts >= iv[i, 0]) & (ts <= iv[i, 1]))
    if a.noexcl: ff = np.ones(len(ts), bool)   # no fault labels: the whole period is the profile
    prof = profile_fn(uniq, np.bincount(code[ff], minlength=nk))
    fw = np.unique(win[ff]); w0 = int(win.min())
    print(f"[{name}] rows {len(ts):,} | series {nk:,} | profile {int(prof.sum()):,} | fault-free windows {len(fw):,}", flush=True)
    def stats(sl, m, minn):
        c, v = code[sl][m], val[sl][m]
        n = np.bincount(c, minlength=nk); s1 = np.bincount(c, v, nk); s2 = np.bincount(c, v * v, nk)
        with np.errstate(invalid="ignore", divide="ignore"):
            mu = np.where(n > 0, s1 / np.maximum(n, 1), 0.0); sd = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mu * mu, 0.0))
        sg = np.maximum(np.maximum(sd, np.abs(mu) * 0.01), 1e-6); keep = (n >= minn) & prof
        z = np.abs(v - mu[c]) / sg[c]; hit = keep[c] & (z >= K)
        pair = np.unique(c[hit].astype(np.int64) * (int(win.max()) - w0 + 1) + (win[sl][m][hit] - w0))
        fired = np.bincount(pair // (int(win.max()) - w0 + 1), minlength=nk)
        return mu, sg, keep, fired
    ALL = None
    for Hn, tag in HS:
        out = f"{out_prefix}_L{tag}"; os.makedirs(out, exist_ok=True); n_ok = 0
        for t in tasks:
            s, e = t["win_start"], t["win_end"]; pw = None
            if s is None or (only and t["case_id"] not in only): continue
            if Hn == "all":
                if ALL is None: ALL = stats(slice(None), ff, 30)
                mu, sg, keep, fired = ALL; nW = len(fw)
            elif Hn == "post" or Hn.startswith("near") or Hn.startswith("frac") or Hn.startswith("pct"):   # diagnostics: fault-free windows after the incident only / the N nearest on both sides
                if Hn == "post": chosen = fw[fw > e // W]
                else:   # nearN: the N nearest windows; fracD: N = round(all fault-free windows of this system / D) (same ratio across systems)
                    Nn = (int(Hn[4:]) if Hn.startswith("near") else max(1, int(round(len(fw) * int(Hn[3:]) / 100))) if Hn.startswith("pct")
                          else max(1, int(round(len(fw) / int(Hn[4:])))))   # pctP: the P % of all fault-free windows nearest the incident
                    c0 = ((s + e) // 2) // W; chosen = np.sort(fw[np.argsort(np.abs(fw - c0), kind="stable")[:Nn]])
                if not len(chosen): continue
                mu, sg, keep, fired = stats(slice(None), ff & np.isin(win, chosen), a.minn); nW = len(chosen); pw = chosen
            else:
                before = fw[: np.searchsorted(fw, (s - 1) // W, side="right")][-int(Hn):]
                if not len(before): continue
                lo, hi = np.searchsorted(ts, before[0] * W), np.searchsorted(ts, s); sl = slice(lo, hi)
                mu, sg, keep, fired = stats(sl, ff[sl], a.minn); nW = len(before); pw = before
            lo, hi = np.searchsorted(ts, s), np.searchsorted(ts, e, side="right")
            c, v, tt = code[lo:hi], val[lo:hi], ts[lo:hi]; k = keep[c]; c, v, tt = c[k], v[k], tt[k]
            z = np.abs(v - mu[c]) / sg[c]; rows = []
            df = pd.DataFrame({"c": c, "z": z, "t": tt}); g = df.groupby("c")["z"].max(); on = df[df["z"] >= K].groupby("c")["t"].min()
            for cc, mx in g[g >= K].items():
                en, kp = uniq[cc].split("||", 1)
                rows.append({"entity": en, "kpi": kp, "z_max": round(float(mx), 2), "onset_ts": int(on[cc]), "bg_rate": round(fired[cc] / nW, 5)})
            rows.sort(key=lambda r: (r["bg_rate"], -r["z_max"]))
            ent_best = {}
            for r in rows:
                if r["entity"] not in ent_best: ent_best[r["entity"]] = r
            rank = sorted((v_ for k_, v_ in ent_best.items() if k_ in catalog), key=lambda r: (r["bg_rate"], -r["z_max"]))
            logs = json.load(open(f"{orig_dir}/{t['case_id']}.json")).get("logs", {}) if orig_dir else {}
            case = {**{k_: t[k_] for k_ in ("case_id", "task_index", "win_start", "win_end", "asks", "n_failures", "instruction")}, "gt": t["gt"], "fired": rows[:400],
                    "entity_rank": [{"entity": r["entity"], "best_bg": r["bg_rate"], "best_kpi": r["kpi"], "onset_ts": r["onset_ts"], "z": r["z_max"]} for r in rank], "logs": logs,
                    "profile_windows": None if pw is None else [int(x) for x in pw]}
            json.dump(case, open(f"{out}/{t['case_id']}.json", "w"), ensure_ascii=False); n_ok += 1
        print(f"[{name}] {tag}: {n_ok} cases -> {out}", flush=True)

if a.dataset in ("bank", "telecom"):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "readers", "OpenRCA")))
    import importlib; R = importlib.import_module(a.dataset)
    tasks = [json.loads(l) for l in open(f"{HERE}/output/query_tasks_{a.dataset}.jsonl")]
    days = sorted(os.path.basename(d) for d in glob.glob(os.path.join(R.SYS_DIR, "telemetry", "*")) if os.path.isdir(d))
    files = ("metric_container.csv",) if a.dataset == "bank" else ("metric_container.csv", "metric_middleware.csv", "metric_node.csv", "metric_service.csv")
    def load_day(d):   # the profile's metric files only (build_metrics_v2.py: container; build_metrics_v2_multi.py telecom: container, middleware, node, service)
        parts = []
        for name in files:
            f = os.path.join(R.SYS_DIR, "telemetry", d, "metric", name)
            if not os.path.exists(f): continue
            if a.dataset == "bank":
                first = open(f).readline(); df = pd.read_csv(f, header=None if first[:1].isdigit() else 0, names=["timestamp", "entity", "kpi", "value"], dtype={"timestamp": np.int64, "value": np.float64})
            else:
                df = pd.read_csv(f, usecols=["timestamp", "value", "cmdb_id", "name"]).rename(columns={"cmdb_id": "entity", "name": "kpi"})
                df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce"); df["value"] = pd.to_numeric(df["value"], errors="coerce"); df = df.dropna(subset=["timestamp", "value"])
                df.loc[df["timestamp"] > 1e12, "timestamp"] //= 1000
            parts.append(df)
        return pd.concat(parts, ignore_index=True) if parts else None
    # fault intervals of the profile builders: normal-splits extract+eval case windows +-300 s (Bank: unmerged as build_metrics_v2.py, Telecom: merged as build_metrics_v2_multi.py)
    SD = os.path.join(HERE, "..", "normal-splits", "OpenRCA_" + a.dataset.capitalize())
    UNK = set(json.load(open(a.unknown_ids))) if a.unknown_ids else set(); PFX = {"bank": "qb", "telecom": "qt"}[a.dataset]
    cid_of = lambda p: f"{PFX}_{int(os.path.basename(p)[:-5].rsplit('_', 1)[1]):03d}"   # normal-splits file index = case id number (checked 09-30: 136/136, 51/51)
    ex = sorted((json.load(open(p))["window"]["start"] - 300, json.load(open(p))["window"]["end"] + 300) for p in glob.glob(f"{SD}/extract/*.json") + glob.glob(f"{SD}/eval/*.json") if cid_of(p) not in UNK)
    if UNK: print(f"[{a.dataset}] excluded incident windows (known) {len(ex)} | not excluded (unknown) {len(UNK)}", flush=True)
    if a.dataset == "telecom":
        m = [list(ex[0])]
        for s_, e_ in ex[1:]:
            if s_ <= m[-1][1]: m[-1][1] = max(m[-1][1], e_)
            else: m.append([s_, e_])
        ex = m
    build(a.dataset, load_day, days, tasks, set(json.load(open(f"{HERE}/output/component_catalog_{a.dataset}.json"))),
          lambda uniq, nff: nff >= 30, f"{HERE}/output/cases_query_{a.dataset}", f"{HERE}/output/cases_query_{a.dataset}", np.array(ex, dtype=np.int64))
else:
    B = os.path.normpath(os.path.join(HERE, "..", "..", "baseline-cache"))
    for ds in ("market1", "market2"):
        spec = importlib.util.spec_from_file_location("ld", f"{B}/datasets/{ds}/loader_{ds}.py"); ld = importlib.util.module_from_spec(spec); spec.loader.exec_module(ld)
        tasks = [json.loads(l) for l in open(f"{B}/datasets/{ds}/query_tasks_{ds}.jsonl")]
        wins = [(t["win_start"], t["win_end"]) for t in tasks if t["win_start"]]
        days = list(ld.window_dates(min(s for s, _ in wins) - 86400, max(e for _, e in wins) + 86400))
        ST = set(json.load(open(f"{HERE}/output/kpi_discrim_stats_{ds}.json")))
        UNK = set(json.load(open(a.unknown_ids))) if a.unknown_ids else set()
        exm = np.array(sorted((t["win_start"] - 300, t["win_end"] + 300) for t in tasks if t["win_start"] is not None and t["case_id"] not in UNK), dtype=np.int64) if UNK else None
        if UNK: print(f"[{ds}] excluded incident windows (known) {len(exm)} | not excluded (unknown) {sum(t['case_id'] in UNK for t in tasks)}", flush=True)
        build(ds, ld.load_metric_date, days, tasks, set(json.load(open(f"{B}/datasets/{ds}/component_catalog_{ds}.json"))),
              lambda uniq, nff: np.array([u in ST for u in uniq]), None, f"{HERE}/output/cases_query_{ds}_full", exm)

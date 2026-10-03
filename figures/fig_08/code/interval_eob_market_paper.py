"""Market cases for the profiling-period sweep under the rule of the paper's Market input (build_market_stats_full.py and
build_market_cases_full.py with MARKET_KEEP_ZEROSIGMA=1). For each incident, mu, sigma and the EOB are recomputed from only the fault-free windows
closest to the incident (N windows: round(all / D) with "<D>:tag", the N nearest with "n<N>:tag", P percent with "p<P>:tag"). As in the paper's
statistics file, the EOB uses the unrounded mu and sigma = max(sd, 1 %|mu|), and the diagnosis z uses mu and sigma rounded to 4 decimals, so a
series whose sigma rounds to 0 gets z = inf when its value differs from the rounded mu. D = 1 reads the statistics file itself (the paper's input).
Fault-free windows are 10 minutes long. Output: output/cases_query_market{1,2}_full_L<tag>/.
Usage: RCA_DATASETS=<raw> python3 interval_eob_market_paper.py --H p100:PP100 p90:PP90 2:PD2 ... [--only ids]"""
import json, os, sys, argparse, importlib.util
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.normpath(os.path.join(HERE, "..", "..", "baseline-cache")); K = 3.0; W = 600   # 10-minute fault-free windows (s)
ap = argparse.ArgumentParser(); ap.add_argument("--H", nargs="+", required=True); ap.add_argument("--only", default=None); a = ap.parse_args()
only = set(json.load(open(a.only))) if a.only else None
for ds in ("market1", "market2"):
    spec = importlib.util.spec_from_file_location("ld", f"{B}/datasets/{ds}/loader_{ds}.py"); ld = importlib.util.module_from_spec(spec); spec.loader.exec_module(ld)
    tasks = [json.loads(l) for l in open(f"{B}/datasets/{ds}/query_tasks_{ds}.jsonl")]
    CAT = set(json.load(open(f"{B}/datasets/{ds}/component_catalog_{ds}.json"))); ST = json.load(open(f"{HERE}/output/kpi_discrim_stats_{ds}.json"))
    wins = [(t["win_start"], t["win_end"]) for t in tasks if t["win_start"]]
    days = list(ld.window_dates(min(s for s, _ in wins) - 86400, max(e for _, e in wins) + 86400))
    M = pd.concat([x[["timestamp", "entity", "kpi", "value"]] for x in (ld.load_metric_date(d) for d in days) if x is not None and len(x)], ignore_index=True).dropna(subset=["timestamp", "value"])
    M["timestamp"] = M["timestamp"].astype(np.int64); M = M.sort_values("timestamp", kind="stable").reset_index(drop=True)
    code, uniq = pd.factorize(M["entity"].astype(str) + "||" + M["kpi"].astype(str)); nk = len(uniq)
    ts = M["timestamp"].values; val = M["value"].values.astype(float); win = ts // W; del M
    ex = np.array(sorted((s - 300, e + 300) for s, e in wins), dtype=np.int64)
    i = np.clip(np.searchsorted(ex[:, 0], ts, side="right") - 1, 0, len(ex) - 1); ff = ~((ts >= ex[i, 0]) & (ts <= ex[i, 1]))
    fw = np.unique(win[ff]); inST = np.array([u in ST for u in uniq])
    stMu = np.array([ST[u]["mu"] if u in ST else np.nan for u in uniq]); stSg = np.array([ST[u]["sigma"] if u in ST else np.nan for u in uniq])
    stDeg = np.array([bool(ST[u].get("degenerate")) if u in ST else False for u in uniq]); stBg = np.array([ST[u]["bg_rate"] if u in ST else np.nan for u in uniq])
    for spec_ in a.H:
        Dd, tag = spec_.split(":"); ABS = Dd.startswith("n"); PCT = Dd.startswith("p"); Dd = int(Dd.lstrip("np")); out = f"{HERE}/output/cases_query_{ds}_full_L{tag}"; os.makedirs(out, exist_ok=True); n_ok = 0   # "n<N>:tag" = the N nearest windows (absolute length)
        for t in tasks:
            s, e = t["win_start"], t["win_end"]
            if s is None or (only and t["case_id"] not in only): continue
            pw = None
            if Dd == 1 and not ABS and not PCT: mu, sg, keep, bg = stMu, stSg, inST, stBg
            else:
                Nn = Dd if ABS else (max(1, int(round(len(fw) * Dd / 100))) if PCT else max(1, int(round(len(fw) / Dd)))); c0 = ((s + e) // 2) // W; chosen = np.sort(fw[np.argsort(np.abs(fw - c0), kind="stable")[:Nn]])   # p<P>: P % of all windows
                m = ff & np.isin(win, chosen); c, v = code[m], val[m]
                n = np.bincount(c, minlength=nk); s1 = np.bincount(c, v, nk); s2 = np.bincount(c, v * v, nk)
                # the paper's statistics file rule, identified on all 5,500 Market1 series: EOB from the unrounded mu and
                # sigma = max(sd, 1 %|mu|); the file (and so the diagnosis z) keeps mu and sigma rounded to 4 decimals, so a series whose
                # sigma rounds to 0 gets z = inf whenever its value differs from the rounded mu (as the paper input does)
                mu_raw = np.where(n > 0, s1 / np.maximum(n, 1), 0.0); sd = np.sqrt(np.maximum(s2 / np.maximum(n, 1) - mu_raw * mu_raw, 0.0))
                sg_raw = np.maximum(sd, np.abs(mu_raw) * 0.01); keep = (n >= 30) & inST
                with np.errstate(divide="ignore", invalid="ignore"): z = np.abs(v - mu_raw[c]) / sg_raw[c]
                mu = np.round(mu_raw, 4); sg = np.round(sg_raw, 4)
                hit = keep[c] & (z >= K); w0 = int(win.min()); span = int(win.max()) - w0 + 1
                fired = np.bincount(np.unique(c[hit].astype(np.int64) * span + (win[m][hit] - w0)) // span, minlength=nk)
                bg = np.round(fired / len(np.unique(win[m])), 5); pw = chosen
            lo, hi = np.searchsorted(ts, s), np.searchsorted(ts, e, side="right"); cc, vv, tt = code[lo:hi], val[lo:hi], ts[lo:hi]
            k = keep[cc]; cc, vv, tt = cc[k], vv[k], tt[k]
            with np.errstate(divide="ignore", invalid="ignore"): zz = np.abs(vv - mu[cc]) / sg[cc]
            df = pd.DataFrame({"c": cc, "z": zz, "t": tt}); g = df.groupby("c")["z"].max(); on = df[df["z"] >= K].groupby("c")["t"].min()
            rows = [{"entity": uniq[q].split("||", 1)[0], "kpi": uniq[q].split("||", 1)[1], "z_max": round(float(mx), 2), "onset_ts": int(on[q]), "bg_rate": float(bg[q])} for q, mx in g[g >= K].items()]
            rows.sort(key=lambda r: (r["entity"], r["kpi"]))   # the paper builder appends signals in groupby(["entity", "kpi"]) order; ties below keep it (adservice first)
            rows.sort(key=lambda r: (bool(r.get("degenerate")), r["bg_rate"], -r["z_max"]))
            ent_best = {}
            for r in rows:
                if r["entity"] not in ent_best: ent_best[r["entity"]] = r
            rank = sorted((x for q, x in ent_best.items() if q in CAT), key=lambda r: (r["bg_rate"], -r["z_max"]))
            case = {**{q: t[q] for q in ("case_id", "task_index", "win_start", "win_end", "asks", "n_failures", "instruction")}, "gt": t["gt"], "fired": rows[:400],
                    "entity_rank": [{"entity": r["entity"], "best_bg": r["bg_rate"], "best_kpi": r["kpi"], "onset_ts": r["onset_ts"], "z": r["z_max"]} for r in rank], "logs": {},
                    "profile_windows": None if pw is None else [int(x) for x in pw]}
            json.dump(case, open(f"{out}/{t['case_id']}.json", "w"), ensure_ascii=False); n_ok += 1
        print(f"[{ds}] {tag}: {n_ok} cases", flush=True)

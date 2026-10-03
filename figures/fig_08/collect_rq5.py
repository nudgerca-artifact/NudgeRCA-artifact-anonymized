"""Values of the RQ5 figure, one row per (system, share of all fault-free windows used for profiling): reads data/scores/<run>.txt (the scorer
output of each run, 8 samples per incident) and writes data/rq5_final.csv. d_*_lo / d_*_hi: the 95 % confidence
interval of the change from the entire fault-free period (the error bars): the per-incident avg@8 of the two runs are paired by incident and the
mean difference is bootstrapped over incidents (10,000 resamples, seed 0); responses in data/outputs/. correct_sd / partial_sd: the standard
deviation of the run over its eight repetitions (response k of every incident, figures/common/per_sample.py). 100 %: Telecom and Bank are the paper's evaluation (Table 3; the
recomputation path reproduces the paper's input exactly), Market is rq5r-market-PP100 (the Market builder at 100 %). Telecom halvings are
dbl-telecom-HD<k> (Telecom has no log block and its trace baseline is a same-day mean, so only the metric profile depends on the share).
Usage: python3 collect_rq5.py"""
import csv, json, os, re, statistics, sys, functools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(HERE, "data", "scores")
sys.path.insert(0, os.path.join(HERE, "..", "common")); from per_sample import per_sample, sd   # noqa: E402
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
def outputs(system, src):
    return (os.path.join(ROOT, "nudgerca", "inference", "outputs", "ours", f"{system.lower()}.jsonl") if isinstance(src, tuple)
            else os.path.join(HERE, "data", "outputs", f"{src}.jsonl"))
def per_incident(path):   # per incident: avg@8 Exact and Partial (%)
    from score_openrca_corrected import parse_answer, task_score
    out = {}
    for l in open(path):
        r = json.loads(l); s = [x for x in (task_score(parse_answer(o), r["gt"]) for o in r["outputs"]) if x is not None]
        if s: out[r["case_id"]] = (100 * statistics.mean(1.0 if x >= 1 else 0.0 for x in s), 100 * statistics.mean(s))
    return out
def ci(system, src, ref, B=10000):   # 95 % CI of the change (Exact, Partial) from the entire period: bootstrap over incidents, paired by incident
    if src is ref: return [0.0, 0.0, 0.0, 0.0]
    a, b = per_incident(outputs(system, src)), per_incident(outputs(system, ref)); ids = sorted(set(a) & set(b))
    rng = np.random.default_rng(0); idx = rng.integers(0, len(ids), size=(B, len(ids))); res = []
    for j in (0, 1):
        dlt = np.array([a[i][j] - b[i][j] for i in ids]); m = dlt[idx].mean(axis=1); res += [round(float(np.percentile(m, 2.5)), 2), round(float(np.percentile(m, 97.5)), 2)]
    return res
@functools.lru_cache(None)
def reps(system, src):   # Exact and Partial of each of the eight repetitions of one run (responses in data/outputs/, the paper's runs in nudgerca/)
    return per_sample(os.path.join(ROOT, "nudgerca", "inference", "outputs", "ours", f"{system.lower()}.jsonl") if isinstance(src, tuple)
                      else os.path.join(HERE, "data", "outputs", f"{src}.jsonl"))
HOURS = {"Telecom": 80.3, "Bank": 211.5, "Market": 18.0}   # all fault-free 10-minute windows x 10 min (Market: mean of Market1 117 and Market2 99 windows)
HALF = {1/2: "HD2", 1/4: "HD4", 1/8: "HD8", 1/16: "HD16", 1/32: "HD32", 1/64: "HD64", 1/128: "HD128"}
RUNS = {"Telecom": {1.0: (39.3, 55.3), **{p / 10: f"rq5-telecom-HP{p}0" for p in (9, 8, 7, 6)}, **{f: f"dbl-telecom-{t}" for f, t in HALF.items()}},
        "Bank": {1.0: (48.7, 55.5), **{p / 10: f"rq5-bank-HP{p}0" for p in (9, 8, 7, 6)}, **{f: f"rq5-bank-{t}" for f, t in HALF.items()}},
        "Market": {1.0: "rq5r-market-PP100", **{p / 10: f"rq5r-market-PP{p}0" for p in (9, 8, 7, 6)},
                   **{f: f"rq5r-market-PD{t[2:]}" for f, t in HALF.items() if f >= 1/16}}}
with open(os.path.join(HERE, "data", "rq5_final.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["system", "fraction", "hours", "correct", "partial", "source", "correct_sd", "partial_sd", "d_correct_lo", "d_correct_hi", "d_partial_lo", "d_partial_hi"])
    for s, d in RUNS.items():
        for f, src in sorted(d.items(), key=lambda x: -x[0]):
            if isinstance(src, tuple): (c, p), tag = src, "paper"
            else:
                m = re.search(r"(?:Strict|Exact) ([\d.]+)% \| Partial ([\d.]+)%", open(os.path.join(S, f"{src}.txt")).readline()); c, p, tag = float(m[1]), float(m[2]), src
            E, P = reps(s, src); E0, P0 = reps(s, d[1.0])   # error bars: per repetition, the change from the entire fault-free period
            assert abs(statistics.mean(E) - c) < 0.051 and abs(statistics.mean(P) - p) < 0.051, (s, f, statistics.mean(E), c)
            w.writerow([s, round(f, 6), round(HOURS[s] * f, 2), c, p, tag, round(sd(E), 2), round(sd(P), 2), *ci(s, src, d[1.0])])
print(open(os.path.join(HERE, "data", "rq5_final.csv")).read())

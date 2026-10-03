"""Recompute the ablation ladder (Exact / Partial / component top-1) and write ablation.json."""
import json, os, sys, statistics, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "nudgerca", "inference"))
from score_openrca_corrected import parse_answer, task_score, field_hits
HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.dirname(os.path.dirname(HERE))
EXP = {"telecom": 21, "bank": 56, "market": 60, "aiops": 159}


STEPS = [("1 prior-prep, no adapter", {"_": A + "/baselines/prior-preprocessing/results/qwen3-4b/base__{ds}.jsonl"}),
         ("2 ours-prep, no adapter",  {"_": A + "/nudgerca/inference/outputs/base/{ds}.jsonl"}),
         ("3 + fork",                 {"_": A + "/figures/fig_06/data/outputs/fork/{ds}.jsonl"}),
         ("4 + privilege",            {"_": A + "/figures/fig_06/data/outputs/fork-priv/{ds}.jsonl"}),
         ("5 + graded = ours",        {"_": A + "/nudgerca/inference/outputs/ours/{ds}.jsonl"})]
def agg(p):
    if not os.path.exists(p): return None
    C, P, F = [], [], collections.defaultdict(list)
    for l in open(p):
        r = json.loads(l); ss, hh = [], collections.defaultdict(list)
        for o in r["outputs"]:
            a = parse_answer(o); s = task_score(a, r["gt"])
            if s is None: continue
            ss.append(s)
            for k, v in field_hits(a, r["gt"]).items(): hh[k].append(v)
        if not ss: continue
        C.append(statistics.mean(1 if x >= 1 else 0 for x in ss)); P.append(statistics.mean(ss))
        for k, v in hh.items(): F[k].append(statistics.mean(v))
    if not C: return None
    m = lambda v: statistics.mean(v) * 100 if v else None
    return dict(n=len(C), corr=m(C), part=m(P), comp=m(F["component"]), ncomp=len(F["comp" "onent"]),
                reason=m(F["reason"]), time=m(F["time"]))
out = {}
for lbl, tpl in STEPS:
    out[lbl] = {}
    for ds, ne in EXP.items():
        v = agg((tpl.get(ds) or tpl["_"]).format(ds=ds))
        out[lbl][ds] = v if (v and v["n"] == ne) else None

for lbl in out:
    per = [(out[lbl][ds], EXP[ds]) for ds in EXP if out[lbl][ds]]
    out[lbl]["all"] = (dict(n=sum(n for _, n in per),
                            **{k: sum(v[k] * n for v, n in per if v[k] is not None) /
                                  max(sum(n for v, n in per if v[k] is not None), 1)
                               for k in ("corr", "part", "comp", "reason", "time")})
                       if len(per) == 4 else None)
json.dump(out, open(f"{HERE}/data/ablation.json", "w"), indent=1)
hdr = ["telecom (21)", "bank (56)", "market (60)", "aiops (159)", "all (296)"]
for metric, name in (("corr", "Exact"), ("part", "Partial"), ("comp", "Component top-1")):
    print(f"\n### {name} (%)")
    print(f"{'Step':26s} " + " ".join(f"{h:>13s}" for h in hdr))
    for lbl, _ in STEPS:
        row = []
        for ds in list(EXP) + ["all"]:
            v = out[lbl][ds]
            row.append(f"{v[metric]:.1f}" if (v and v[metric] is not None) else "---")
        print(f"{lbl:26s} " + " ".join(f"{x:>13s}" for x in row))

"""Shared helpers for the table scripts of figures/: the ground truth, the scorer, and the per-incident aggregation.

Convention (every table of the paper): per incident, the mean over its samples (8 for every model run; systems that give one answer
contribute that answer), then the mean over incidents (avg@8). Exact = every asked field right; Partial = the share of asked fields
right; Comp / Fault type / Time = the field accuracy over the queries that ask for that field.
Ground truth: nudgerca/preprocessing/rendered-inputs/cases_eval.jsonl (296 evaluation incidents; the AIOps 2025 queries ask for the
component, the fault type and the occurrence time). Scorer: nudgerca/inference/score_openrca_corrected.py.
"""
import collections, glob, json, os, re, subprocess, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "nudgerca", "inference"))
from score_openrca_corrected import parse_answer, task_score, field_hits, comp_match   # noqa: E402,F401

P = lambda *p: os.path.join(ROOT, *p)
def jl(p): return [json.loads(l) for l in open(p)]
CASES = {r["case_id"]: r for r in jl(P("nudgerca/preprocessing/rendered-inputs/cases_eval.jsonl"))}
DSN = {"qa": "aiops", "qb": "bank", "qm1": "market", "qm2": "market", "qt": "telecom"}
BY = collections.defaultdict(list)
for _c in CASES: BY[DSN[_c.split("_")[0]]].append(_c)
DS = ("telecom", "bank", "market", "aiops"); D3 = DS[:3]
K8S = re.compile(r"^(.*)-[0-9a-f]{6,10}-[a-z0-9]{5}$")
def to_service(p):
    m = K8S.match(str(p)); return m.group(1) if m else str(p)


def load(*paths, rank=False, own_gt=False):
    """Samples per incident -> parsed answers. rank=True: ranking baselines (first component of nezha.rank / kpiroot.rank).
    own_gt=True keeps the ground truth stored in the file (outputs scored on a split other than ours, or on another query)."""
    a, g = {}, {}
    for pat in paths:
        for f in sorted(glob.glob(pat)):
            for r in jl(f):
                cid = r["case_id"]
                if not own_gt and cid not in CASES: continue
                if rank:
                    rk = (r.get("nezha") or r.get("kpiroot") or {}).get("rank") or []
                    t = rk[0] if rk else None
                    if isinstance(t, list): t = t[0]
                    if t and "nezha" in r: t = to_service(t)
                    a[cid] = [{"component": t} if t else {}]
                else:
                    a[cid] = [parse_answer(o) for o in r["outputs"]]
                if own_gt: g[cid] = r["gt"]
    return (a, g) if own_gt else a


def cell(a, cids, gt=None):
    S, F = [], {"component": [], "reason": [], "time": []}
    for c in cids:
        if c not in a: continue
        g = (gt or {}).get(c) or CASES[c]["gt"]
        ss = [s for s in (task_score(x, g) for x in a[c]) if s is not None]
        if not ss: continue
        S.append((sum(1 for s in ss if s >= 1) / len(ss), sum(ss) / len(ss)))
        for k in F:
            hs = [h for h in (field_hits(x, g).get(k) for x in a[c]) if h is not None]
            if hs: F[k].append(sum(hs) / len(hs))
    if not S: return None
    pc = lambda v: (100 * sum(v) / len(v)) if v else None
    return dict(C=100 * sum(x[0] for x in S) / len(S), P=100 * sum(x[1] for x in S) / len(S), c=pc(F["component"]), r=pc(F["reason"]), t=pc(F["time"]), n=len(S))


f1 = lambda x: "-" if x is None else f"{x:.1f}"
cpc = lambda v: "- / - / -" if not v else f"{f1(v['C'])} / {f1(v['P'])} / {f1(v['c'])}"


def run(script, cwd, *argv):
    r = subprocess.run([sys.executable, script, *argv], cwd=cwd, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def emit(lines, here, name):
    """Print the table and write it next to the script as <name>.txt."""
    text = "\n".join(lines) + "\n"
    open(os.path.join(here, name + ".txt"), "w").write(text); print(text, end="")

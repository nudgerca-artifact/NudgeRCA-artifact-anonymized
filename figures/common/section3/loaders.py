"""Shared loader: the Section 3 scripts read the Bank trajectories and their cases (common/section3/data/) through this module.
Each folder stores what it derives from them in its own data/.
"""
import ast, glob, json, os, re, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
V4 = os.path.join(DATA, "bank_trajectories")

BANK_COMPS = ["Tomcat01", "Tomcat02", "Tomcat03", "Tomcat04", "apache01", "apache02",
              "IG01", "IG02", "MG01", "MG02", "Mysql01", "Mysql02", "Redis01", "Redis02"]

# ---------------------------------------------------------------- Bank trajectories (81 incidents x 8)
def _lit(x):
    if isinstance(x, str):
        try: return ast.literal_eval(x)
        except Exception: return x
    return x

def load_v4_cases():
    """uuid -> case dict (metrics.anomalous[entity,kpi,max_z,...], logs, traces, propagation, ground_truth)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(V4, "cases", "*.json"))):
        c = json.load(open(p)); out[c["uuid"]] = c
    return out

def entity_scores_v4(case):
    """Per-entity magnitude score. v4 caps z at 30, so many entities tie on the maximum (10-16 entities per case);
    the OpsAgent-style 'sum of member-signal deviations' is the primary key, max z the secondary. Returns: [(entity, sum_z, max_z, n_signals)] descending."""
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for a in case["metrics"]["anomalous"]:
        z = float(a["max_z"]); e = a["entity"]
        agg[e][0] += z; agg[e][1] = max(agg[e][1], z); agg[e][2] += 1
    rows = [(e, v[0], v[1], v[2]) for e, v in agg.items()]
    rows.sort(key=lambda r: (-r[1], -r[2], r[0]))
    return rows

def load_v4_trajectories(glob_dir=None):
    """648 trajectory rows: uuid, sample(sc_seed), gt_comp, gt_fault, pred(list top-3), fr_rank, won, think, answer_json, top1_desc.
    glob_dir: read the trajectory files of another directory instead (the two files of Figure 3)."""
    rows = []
    for p in sorted(glob.glob(os.path.join(glob_dir or os.path.join(V4, "trajectories"), "*__sc*.json"))):
        r = json.load(open(p))
        gt = _lit(r["gt"]); pred = _lit(r["pred"]) or []
        fr = r.get("fr_rank"); fr = None if fr in (None, "None") else int(fr)
        desc = ""
        try:
            rl = json.loads(r["answer_json"])["rank_list"]; desc = (rl[0].get("description") or "").strip()
        except Exception:
            pass
        rows.append(dict(uuid=r["uuid"], job=r["job"], sample=int(r.get("sc_seed") or 0), gt_comp=gt["component"],
                         gt_fault=gt["fault_type"], pred=list(pred), top1=(pred[0] if pred else None), fr_rank=fr,
                         won=int(r["won"]), think=r.get("think") or "", answer_json=r.get("answer_json") or "",
                         top1_desc=desc, n_gen_tokens=int(r.get("n_gen_tokens") or 0), finish=r.get("finish_reason")))
    return rows

# ---------------------------------------------------------------- answer matching (the scorer's rule: strip the prediction's -number suffix only when the GT has none)
POD_SUF = re.compile(r"-\d+$")
def comp_match(pred, gt):
    p = str(pred).strip(); g = str(gt).strip()
    if not p or not g: return False
    if p == g: return True
    return (not POD_SUF.search(g)) and POD_SUF.sub("", p) == g

def comp_match_any(pred, gts):
    return any(comp_match(pred, g) for g in gts)

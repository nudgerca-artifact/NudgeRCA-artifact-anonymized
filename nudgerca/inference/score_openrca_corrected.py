"""Scoring of the OpenRCA-style queries used throughout the paper (Section 5.1.2), built on the port of the official OpenRCA scorer in
score_openrca_official.py.

- A response is scored as matched elements / requested elements (component, fault type and occurrence time of each failure);
  Exact is the share of responses with every element correct, Partial the mean score.
- The component is compared at the level of the label (an instance name matches a service-level label by its service name), the fault
  type must match the label, and the occurrence time must be within 60 s.
- A label that lists several component names for one failure accepts any of them.
- An answer that lists several faults ({"faults": [...]}) is matched to the labeled faults by the best assignment, as in the official scorer.
- Per-element accuracy (the Component, Fault type and Time columns) counts an element correct if any labeled value matches.

Usage: python3 score_openrca_corrected.py <out_jsonl...> <label>   (several files are scored together)
"""
import json, re, sys, collections, itertools
from score_openrca_official import ep, tier

POD_SUF = re.compile(r"-\d+$")
NARROW = re.compile(r"\{[^{}]*\}", re.DOTALL)

def comp_match(pred, gt_name):
    p = str(pred).strip(); g = str(gt_name).strip()
    if not p or not g: return False
    if p == g: return True
    return (not POD_SUF.search(g)) and POD_SUF.sub("", p) == g

def reason_match(pred, gt_reason):
    return str(pred).strip() == str(gt_reason).strip()

def time_match(pred_ts, gt_ts):
    return pred_ts is not None and abs(pred_ts - gt_ts) <= 60

def parse_answer(text):
    """A single dict is parsed as in the official scorer; the multi-answer schema (a "faults" list) is parsed with nested braces."""
    seg = text[text.rfind("</think>")+1:] if "</think>" in text else text
    if '"faults"' in seg:
        i, j = seg.find("{"), seg.rfind("}")
        if i >= 0 and j > i:
            try:
                a = json.loads(seg[i:j+1])
                if isinstance(a, dict) and isinstance(a.get("faults"), list): return a["faults"]
            except Exception:
                pass
    m = NARROW.search(seg)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}

def is_single_fault_multiname(gt):
    return len(gt.get("components", [])) > 1 and len(gt.get("reasons", [])) <= 1 and len(gt.get("times", [])) <= 1

def task_score(ans, gt):
    """Sample score = matched elements / total elements (with corrections ①②③). None if unscorable."""
    comps, reasons, times = gt["components"], gt["reasons"], gt["times"]
    preds = ans if isinstance(ans, list) else [ans]
    preds = [p for p in preds if isinstance(p, dict)] or [{}]
    if is_single_fault_multiname(gt):
        total = 1 + len(reasons) + len(times)
        p = preds[0]
        pts = int(any(comp_match(p.get("component", ""), g) for g in comps))
        if reasons and reason_match(p.get("reason", ""), reasons[0]): pts += 1
        if times and time_match(ep(p.get("occurrence_time")), times[0]): pts += 1
        return pts / total
    n_fail = max(len(comps), len(reasons), len(times), 1)
    total = len(comps) + len(reasons) + len(times)
    if total == 0: return None
    preds = preds[:n_fail]  # over-listing guard: score only as many answers as faults (listing every candidate would abuse the optimal assignment)
    best = 0
    k = min(len(preds), n_fail)
    for assign in itertools.permutations(range(n_fail), k):
        pts = 0
        for p, i in zip(preds, assign):
            if i < len(comps) and comp_match(p.get("component", ""), comps[i]): pts += 1
            if i < len(reasons) and reason_match(p.get("reason", ""), reasons[i]): pts += 1
            if i < len(times) and time_match(ep(p.get("occurrence_time")), times[i]): pts += 1
        best = max(best, pts)
    return best / total

def field_hits(ans, gt):
    """Lenient per-field judgment (any of several GTs matches); single source for fork-pair labels and field rows."""
    preds = ans if isinstance(ans, list) else [ans]
    preds = [p for p in preds if isinstance(p, dict)] or [{}]
    n_fail = max(len(gt["components"]), len(gt["reasons"]), len(gt["times"]), 1)
    preds = preds[:n_fail]  # same over-listing guard as task_score
    out = {}
    if gt["components"]:
        out["component"] = any(comp_match(p.get("component", ""), g) for p in preds for g in gt["components"])
    if gt["reasons"]:
        out["reason"] = any(reason_match(p.get("reason", ""), g) for p in preds for g in gt["reasons"])
    if gt["times"]:
        out["time"] = any(time_match(ep(p.get("occurrence_time")), g) for p in preds for g in gt["times"])
    return out

def main(paths, label):
    scores = []; by_tier = collections.defaultdict(list)
    fh = collections.defaultdict(list); cases = set()
    for path in paths:
        for l in open(path):
            r = json.loads(l)
            cases.add(r.get("case_id"))
            for t in r["outputs"]:
                a = parse_answer(t)
                s = task_score(a, r["gt"])
                if s is None: continue
                scores.append(s); by_tier[tier(r.get("task_index"))].append(s)
                for k, v in field_hits(a, r["gt"]).items(): fh[k].append(v)
    if not scores: print(f"[{label}] none"); return
    strict = sum(1 for s in scores if s >= 1.0) / len(scores)
    partial = sum(scores) / len(scores)
    tl = " | ".join(f"{k} S:{sum(1 for x in v if x>=1)/len(v)*100:.0f}%/P:{sum(v)/len(v)*100:.0f}%"
                    for k, v in sorted(by_tier.items()))
    fl = " | ".join(f"{k} {sum(v)/len(v)*100:.1f}%" for k, v in sorted(fh.items()))
    print(f"[{label}] Exact {strict*100:.1f}% | Partial {partial*100:.1f}% (samples {len(scores)}, cases {len(cases)})")
    print(f"  fields: {fl}  difficulty: {tl}")

if __name__ == "__main__":
    main(sys.argv[1:-1], sys.argv[-1])

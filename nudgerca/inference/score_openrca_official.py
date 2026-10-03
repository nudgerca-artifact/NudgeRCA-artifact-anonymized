"""Port of the official OpenRCA scoring (logic of microsoft/OpenRCA main/evaluate.py).

- Task score = matched elements / total elements in the rubric (elements = time, component and reason of each failure)
- Time within ±60 s; component and reason by exact string match (case-sensitive)
- Multiple failures: optimal permutation matching of predictions to ground truths (our answer is single, so it is matched
  to the most favorable failure and the other failures' elements stay in the denominator, as in the official rule)
- Exact = share of tasks with score 1.0 / Partial = mean task score
- Difficulty: task_index 1-3 easy, 4-6 middle, 7+ hard (split of the original paper)
Usage: python3 score_openrca_official.py <out_jsonl> <label>
"""
import json, re, sys, collections
from datetime import datetime, timezone, timedelta
TZ = timezone(timedelta(hours=8))
def parse_ans(t):
    seg = t[t.rfind("</think>")+1:] if "</think>" in t else t
    m = re.search(r"\{[^{}]*\}", seg, re.DOTALL)
    try: return json.loads(m.group(0)) if m else {}
    except Exception: return {}
def ep(s):
    try: return int(datetime.strptime(str(s).strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ).timestamp())
    except Exception: return None
def task_score(a, gt):
    """Match the single prediction a to each failure i and keep the best score (1 point per element)."""
    n_fail = max(len(gt["components"]), len(gt["reasons"]), len(gt["times"]), 1)
    total = len(gt["components"]) + len(gt["reasons"]) + len(gt["times"])
    if total == 0: return None
    best = 0
    pc = str(a.get("component", "")).strip()
    pr = str(a.get("reason", "")).strip()
    pt = ep(a.get("occurrence_time"))
    for i in range(n_fail):
        pts = 0
        if i < len(gt["components"]) and pc == gt["components"][i]: pts += 1
        if i < len(gt["reasons"]) and pr == gt["reasons"][i]: pts += 1
        if i < len(gt["times"]) and pt is not None and abs(pt - gt["times"][i]) <= 60: pts += 1
        best = max(best, pts)
    return best / total
def tier(task_index):
    try: n = int(str(task_index).split("_")[1])
    except Exception: return "?"
    return "easy" if n <= 3 else ("middle" if n <= 6 else "hard")
def main(path, label):
    scores = []; by_tier = collections.defaultdict(list)
    for l in open(path):
        r = json.loads(l)
        for t in r["outputs"]:
            s = task_score(parse_ans(t), r["gt"])
            if s is None: continue
            scores.append(s); by_tier[tier(r.get("task_index"))].append(s)
    if not scores: print(f"[{label}] none"); return
    strict = sum(1 for s in scores if s >= 1.0) / len(scores)
    partial = sum(scores) / len(scores)
    line = " | ".join(f"{k} S:{sum(1 for x in v if x>=1)/len(v)*100:.0f}%/P:{sum(v)/len(v)*100:.0f}%"
                      for k, v in sorted(by_tier.items()))
    print(f"[{label}] Exact {strict*100:.1f}% | Partial {partial*100:.1f}%  (samples {len(scores)})  difficulty: {line}")
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

"""Select excerpt candidates for Figure behavior (b): failed trajectories with the pattern 'carried out the procedure but fell back on magnitude at the decision'.
Conditions (adjudicated verdicts): won=0, q2_prop=yes, f_gt_considered=yes, q4_mag_rationale=yes (m2_self_contra=yes first).
Output: data/candidates.json (job, uuid, gt, top1, verdicts, length of the raw reasoning); the final choice is made by hand and render_excerpt.py produces the tex."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common", "section3"))
import loaders as L
adj = {}
p = os.path.join(HERE, "..", "section_3", "behavior_judge", "data", "adjudicated.jsonl")
for l in open(p):
    if l.strip(): r = json.loads(l); adj[r["job"]] = r
traj = {t["job"]: t for t in L.load_v4_trajectories()}
cands = []
for j, r in adj.items():
    t = traj[j]
    if t["won"] or r.get("q2_prop") != "yes" or r.get("f_gt_considered") != "yes" or r.get("q4_mag_rationale") != "yes": continue
    cands.append(dict(job=j, uuid=t["uuid"], gt=t["gt_comp"], gt_fault=t["gt_fault"], top1=t["top1"], pred=t["pred"], fr_rank=t["fr_rank"],
                      m2_self_contra=r.get("m2_self_contra"), m1_premature=r.get("m1_premature"), think_chars=len(t["think"]), top1_desc=t["top1_desc"]))
cands.sort(key=lambda c: (c["m2_self_contra"] != "yes", c["think_chars"]))
json.dump(cands, open(os.path.join(HERE, "data", "candidates.json"), "w"), indent=1, ensure_ascii=False)
print(len(cands), "candidates;", sum(1 for c in cands if c["m2_self_contra"] == "yes"), "with self-contradiction")
for c in cands[:5]: print(c["job"], c["gt"], "->", c["top1"], c["think_chars"], "|", c["top1_desc"][:100])

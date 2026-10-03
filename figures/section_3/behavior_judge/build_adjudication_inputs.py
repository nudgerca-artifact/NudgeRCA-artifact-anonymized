"""Adjudication inputs for disagreements: a third reviewer (C) judges only the (job, question) pairs on which reviewers A and B disagree. Chunk = 12 jobs.
Input: data/disagreements.jsonl (output of aggregate.py). Output: data/adjudication_inputs/adj_XX.md + index.json
C's output: data/adjudication/adj_XX.jsonl: {"job":..., "<q>":"yes|no", ...} for the disputed questions only."""
import json, os, sys, collections, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "common", "section3"))
import loaders as L
from build_judge_inputs import case_header, traj_block
OUT = os.path.join(HERE, "data", "adjudication_inputs"); os.makedirs(OUT, exist_ok=True)
dis = collections.defaultdict(list)
for l in open(os.path.join(HERE, "data", "disagreements.jsonl")):
    if l.strip(): d = json.loads(l); dis[d["job"]].append(d)
traj = {t["job"]: t for t in L.load_v4_trajectories()}
jobs = sorted(dis); index = []
for i in range(0, len(jobs), 12):
    cid = f"adj_{i//12:02d}"; parts = []; seen = set()
    for j in jobs[i:i+12]:
        t = traj[j]
        if t["uuid"] not in seen: parts.append(case_header(t["uuid"])); seen.add(t["uuid"])
        q = "\n".join(f"- DISPUTED {d['q']}: reviewer A said {d['A']} (quote: {d['quoteA']!r}); reviewer B said {d['B']} (quote: {d['quoteB']!r})" for d in dis[j])
        parts.append(traj_block(t) + "\nQUESTIONS TO ADJUDICATE FOR THIS TRAJECTORY:\n" + q + "\n")
    open(os.path.join(OUT, cid + ".md"), "w").write("\n\n".join(parts))
    index.append(dict(chunk=cid, jobs=jobs[i:i+12], n_items=sum(len(dis[j]) for j in jobs[i:i+12])))
json.dump(index, open(os.path.join(OUT, "index.json"), "w"), indent=1)
print(len(jobs), "jobs with disagreements,", sum(len(v) for v in dis.values()), "items,", len(index), "chunks")

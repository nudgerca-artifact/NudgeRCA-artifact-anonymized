#!/usr/bin/env python3
"""Section 3.2 numbers: behaviors observed in the untrained Qwen3-4B trajectories on Bank (Behavior-1 to 3), the agreement and Cohen's
kappa of the two judge runs, and the numbers on the first-listed candidate and on FoundRoot-14B.

- behavior_judge/data/adjudicated.jsonl: 640 trajectories (80 Bank incidents x 8; the one case whose final answer cannot be read is left
  out), nine yes / no questions judged by two independent reviewer runs and adjudicated by a third; agreement in data/agreement.json.
- input_vs_model_split/split_by_input_group.py: the same trajectories split by whether the root cause is in the top group by summed
  deviation.
- input_vs_model_split/rank1_follow.py: the first-listed candidate on the fault-free-rarity input (untrained Qwen3-4B, evaluation cases
  that ask for the component).
- input_vs_model_split/foundroot_prominence.py: FoundRoot-14B on its authors' released input (55 shared incidents).
Usage: python3 section3_numbers.py   -> section3_numbers.txt
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from tables import emit, jl, run   # noqa: E402

J = os.path.join(HERE, "behavior_judge", "data"); S = os.path.join(HERE, "input_vs_model_split")
ADJ = [r for r in jl(os.path.join(J, "adjudicated.jsonl")) if "openrca_bank_1615319040_62" not in r["job"]]
pct = lambda k: 100 * sum(1 for r in ADJ if r[k] == "yes") / len(ADJ)
out = [f"All {len(ADJ)} trajectories: examines two or more candidates {pct('q1_scan'):.0f}, reasons about propagation {pct('q2_prop'):.0f}, "
       f"largest anomaly as the stated rationale {pct('q4_mag_rationale'):.0f}, own analysis points to another component {pct('m2_self_contra'):.0f}, "
       f"cites another component's signal {pct('q3_ungrounded'):.0f}, correct component {100 * sum(r['won'] for r in ADJ) / len(ADJ):.0f} (%).", ""]
AG = json.load(open(os.path.join(J, "agreement.json")))["table"]
def judge_run(name):   # the per-trajectory answers of one judge run
    rows = {}
    for f in sorted(os.listdir(os.path.join(J, "judge_outputs", name))):
        for r in jl(os.path.join(J, "judge_outputs", name, f)): rows[r["job"]] = r
    return rows
RA, RB = judge_run("A"), judge_run("B"); JOBS = sorted(set(RA) & set(RB)); KAP = []
for q in ("q1_scan", "q2_prop", "q3_ungrounded", "q4_mag_rationale", "q5_causal_chain", "f_gt_considered", "m1_premature", "m2_self_contra", "m3_stop_after_commit"):
    a = [RA[j][q] == "yes" for j in JOBS]; b = [RB[j][q] == "yes" for j in JOBS]; n = len(JOBS)
    po = sum(x == y for x, y in zip(a, b)) / n; pa, pb = sum(a) / n, sum(b) / n; pe = pa * pb + (1 - pa) * (1 - pb)
    yes_both = min(sum(a), sum(b))
    KAP.append(f"{q} {'n/a (all yes)' if pe >= 1 else f'{(po - pe) / (1 - pe):.2f}'}" + (f" (yes in {sum(a)} / {sum(b)} of {n})" if yes_both < 0.02 * n else ""))
out.append("Agreement between the two judge runs per question: " + ", ".join(f"{k} {100 * v['agreement']:.0f}%" for k, v in AG.items() if "agreement" in v) + ".")
out.append("Cohen's kappa between the two judge runs per question (questions answered yes in almost no trajectory have kappa near 0 by construction): " + ", ".join(KAP) + ".")
out += ["", "Split by whether the cause is in the top group by summed deviation:", run("split_by_input_group.py", S),
        "", "The first-listed candidate on the fault-free-rarity input (evaluation cases that ask for the component):", run("rank1_follow.py", S),
        "", "FoundRoot-14B on its authors' released input (55 shared incidents):", run("foundroot_prominence.py", S)]
emit(out, HERE, "section3_numbers")

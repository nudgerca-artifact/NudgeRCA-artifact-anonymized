#!/usr/bin/env python3
"""Table 4: FoundRoot's four test sets (RQ3); FoundRoot-14B on its authors' input, NudgeRCA-4B on our preprocessing, zero-shot.

Same incidents and observation window as the authors' inputs, each system with its own preprocessing; the bundle scorer for both.
FoundRoot-14B on DejaVu-A, DejaVu-B and Eadro-SN answers the authors' problem text with a paragraph that asks for the occurrence time
and a fault type from the closed vocabulary; on GAIA it answers the authors' test problems unchanged (component only; GAIA has no fault type or
time labels). NudgeRCA-4B = Qwen3-4B with the bank adapter of baselines/foundroot/ours-preprocessing-on-foundroot-benchmark/adapter/,
no training on any of these systems, on our Top-10 render built from the raw telemetry, 8 samples. Denominators 63 / 90 / 10 / 255; the
Eadro case whose 57 s window fired no signal has no prompt and counts as wrong.
Usage: python3 table_04.py   -> table_04.txt
"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from tables import P, comp_match, emit, f1, field_hits, jl, parse_answer, task_score   # noqa: E402

NP = P("baselines/foundroot/ours-preprocessing-on-foundroot-benchmark")
NCASES = collections.defaultdict(dict)
for L in "ABCD":
    for r in jl(f"{NP}/cases/cases_{L}.jsonl"): NCASES[L][r["case_id"]] = r

def agg_cases(answers, L):
    """A case without an answer counts as wrong on every asked field; denominator = all cases of the set."""
    S = []; F = {"component": [], "reason": [], "time": []}
    for cid, c in NCASES[L].items():
        outs = answers.get(cid, [])
        ss = [v for v in (task_score(x, c["gt"]) for x in outs) if v is not None]
        S.append((sum(1 for v in ss if v >= 1) / len(ss), sum(ss) / len(ss)) if ss else (0.0, 0.0))
        for k in F:
            hs = [h for h in (field_hits(x, c["gt"]).get(k) for x in outs) if h is not None]
            if hs: F[k].append(sum(hs) / len(hs))
            elif k in c["asks"]: F[k].append(0.0)
    pc = lambda v: (100 * sum(v) / len(v)) if v else None
    return dict(C=100 * sum(x[0] for x in S) / len(S), P=100 * sum(x[1] for x in S) / len(S), c=pc(F["component"]), r=pc(F["reason"]), t=pc(F["time"]))

def agg_rows(rows):
    """One answer per case; the FoundRoot files carry their own ground truth."""
    S = []; F = {"component": [], "reason": [], "time": []}
    for a, gt in rows:
        v = task_score(a, gt)
        if v is None: continue
        S.append(v)
        for k, h in field_hits(a, gt).items():
            if h is not None: F[k].append(h)
    pc = lambda v: (100 * sum(v) / len(v)) if v else None
    return dict(C=100 * sum(1 for v in S if v >= 1) / len(S), P=100 * sum(S) / len(S), c=pc(F["component"]), r=pc(F["reason"]), t=pc(F["time"]))

from foundroot_answer import parse_answer as FP   # the answer format of FoundRoot (rank_list, reason, occurrence_time)
def fr_answer(raw):
    a = FP(raw)
    if isinstance(a, dict) and a.get("rank_list"):
        rl = a["rank_list"]; c0 = rl[0] if rl and isinstance(rl[0], dict) else {}
        return {"component": str(c0.get("component", "")).strip(), "reason": str(a.get("reason", "")).strip(), "occurrence_time": str(a.get("occurrence_time", "")).strip()}
    return a if isinstance(a, dict) else {}

FRB = collections.defaultdict(list)
for r in jl(f"{NP}/results/foundroot-14b__AB.jsonl"): FRB[{"A1": "A", "A2": "B"}[r["task_index"].split(":")[0]]].append((fr_answer(r["raw"]), r["gt"]))
for r in jl(f"{NP}/results/foundroot-14b__C.jsonl"): FRB["C"].append((fr_answer(r["raw"]), r["gt"]))
SOL = {}
for L in "ABCD":
    for r in jl(f"{NP}/authors-data/{L}/test.jsonl"): SOL[f"{L}:{r['case_idx']}"] = json.loads(r["solution"])["root_cause"]
FRT = collections.defaultdict(lambda: [0, 0])
for r in jl(f"{NP}/results/foundroot-14b__authors-test-ABCD.jsonl"):
    L = r["case_id"].split(":")[0]; a = fr_answer(r["raw"]); FRT[L][1] += 1; FRT[L][0] += any(comp_match(a.get("component", ""), g) for g in SOL[r["case_id"]])
OURS8 = {L: {r["case_id"]: [parse_answer(o) for o in r["outputs"]] for r in jl(f"{NP}/results/ours-bank__{L}.jsonl")} for L in "ABCD"}
SETN = {"A": "DejaVu-A", "B": "DejaVu-B", "C": "Eadro-SN", "D": "GAIA"}
f2 = lambda x: "-" if x is None else f"{x:.2f}"
# the paper rounds half up (71.25 -> 71.3); the shared f1 of common/tables.py rounds half to even
from decimal import Decimal, ROUND_HALF_UP
f1 = lambda x: "-" if x is None else str(Decimal(repr(float(x))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
out = ["| Dataset (incidents) | System | Exact | Partial | Comp. | Type | Time |", "|---|---|---|---|---|---|---|"]
for L in "ABCD":
    if L == "D": out.append(f"| {SETN[L]} ({len(NCASES[L])}) | FoundRoot-14B | - | - | {f1(100 * FRT['D'][0] / FRT['D'][1])} | - | - |")
    else:
        v = agg_rows(FRB[L]); out.append(f"| {SETN[L]} ({len(NCASES[L])}) | FoundRoot-14B | {f1(v['C'])} | {f1(v['P'])} | {f1(v['c'])} | {f1(v['r'])} | {f1(v['t'])} |")
    v8 = agg_cases(OURS8[L], L)
    if L == "D": out.append(f"| | NudgeRCA-4B | - | - | {f1(v8['c'])} | - | - |")
    else: out.append(f"| | NudgeRCA-4B | {f1(v8['C'])} | {f1(v8['P'])} | {f1(v8['c'])} | {f1(v8['r'])} (exact {f2(v8['r'])}) | {f1(v8['t'])} (exact {f2(v8['t'])}) |")
emit(out, HERE, "table_04")

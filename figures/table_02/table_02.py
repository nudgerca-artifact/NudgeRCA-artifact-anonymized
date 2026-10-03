#!/usr/bin/env python3
"""Table 2: datasets and the scope of training and evaluation (incident counts).

Within-system sets: nudgerca/preprocessing/rendered-inputs/splits/<dataset>.json (train_pool / eval). Held-out datasets (RQ3, the four
test benchmarks of FoundRoot): baselines/foundroot/ours-preprocessing-on-foundroot-benchmark/cases/.
Usage: python3 table_02.py   -> table_02.txt
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from tables import DS, P, emit, jl   # noqa: E402

NAME = {"telecom": ("Telecom", "Telecom service"), "bank": ("Bank", "Banking service"), "market": ("Market", "HipsterShop"),
        "aiops": ("AIOps 2025", "HipsterShop")}
out = ["| Dataset | System | Train | Eval. |", "|---|---|---|---|", "| *Training and evaluation within each system* | | | |"]
for d in DS:
    s = json.load(open(P(f"nudgerca/preprocessing/rendered-inputs/splits/{d}.json")))
    tr = s.get("train_pool") or s.get("train"); ev = s.get("eval")
    out.append(f"| {NAME[d][0]} | {NAME[d][1]} | {len(tr)} | {len(ev)} |")
out.append("| *Evaluation on held-out datasets* | | | |")
FR = P("baselines/foundroot/ours-preprocessing-on-foundroot-benchmark")
for L, nm, sysname in zip("ABCD", ("DejaVu-A", "DejaVu-B", "Eadro-SN", "GAIA"),
                          ("Major ISP system", "Major ISP system", "SocialNetwork", "MicroSS")):
    out.append(f"| {nm} | {sysname} | - | {len(jl(f'{FR}/cases/cases_{L}.jsonl'))} |")
emit(out, HERE, "table_02")

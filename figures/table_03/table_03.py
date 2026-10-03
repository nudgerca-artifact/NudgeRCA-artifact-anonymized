#!/usr/bin/env python3
"""Table 3: accuracy on the four benchmarks (Exact / Partial, %), NudgeRCA and the baselines.

Exact: the share of responses that answer every requested element correctly. Partial: the mean share of requested elements answered
correctly per response. Per incident the mean over its samples, then the mean over incidents (figures/common/tables.py).
Inputs: nudgerca/inference/outputs/ours/ (NudgeRCA-4B, 8 samples) and baselines/*/ (see baselines/README.md).
- Nezha, KPIRoot, KPIRoot+, Statistical EOB and ThinkFL answer a component only; their Partial counts the other requested elements as wrong.
- Statistical EOB: the first candidate of the NudgeRCA input (baselines/statistical-eob/), scored with the ground truth of that input.
- RCA-Agent: one run per incident with the released code. GPT-5-mini on Telecom, Bank and Market: the runs of
  baselines/openrca-agent/results/prior-runs/, joined to our incidents by the query text; GPT-5-mini on AIOps 2025 and Solar Pro 4:
  our runs with baselines/openrca-agent/run_rca_agent.py (results/gpt-5-mini/, results/solar-pro4/), whose AIOps 2025 query asks for
  the component and the fault type and is scored on those two elements.
- ThinkFL-8B: the released checkpoint with the released prompt and tool computation, 8 samples.
- OpsAgent-14B: the authors' released outputs on their own split (Telecom 20, Bank 54, Market 59); no AIOps 2025 outputs.
Usage: python3 table_03.py   -> table_03.txt
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from tables import BY, DS, P, cell, f1, emit, load   # noqa: E402

B = lambda *p: P("baselines", *p)
OURS = load(*[P("nudgerca/inference/outputs/ours", f"{d}.jsonl") for d in DS])
PRIOR = load(B("prior-preprocessing/results/qwen3-4b/base__*.jsonl"))
NEZHA = load(*[B(f"nezha/results/ours/{d}.jsonl") for d in DS], rank=True)
KPIROOT = load(B("kpiroot/results/kpiroot__*.jsonl"), rank=True)
KPIROOTP = load(B("kpiroot/results/kpirootplus__*.jsonl"), rank=True)
EOB, EOB_GT = load(B("statistical-eob/results/*.jsonl"), own_gt=True)
REACT = load(B("react/outputs/react_*.jsonl"))
GPT5M = load(B("openrca-agent/results/prior-runs/*__gpt-5-mini.jsonl"))
GPT5M_A, GPT5M_GT = load(B("openrca-agent/results/gpt-5-mini/aiops.jsonl"), own_gt=True)
SOLAR4, SOLAR4_GT = load(B("openrca-agent/results/solar-pro4/*.jsonl"), own_gt=True)
THINKFL8 = load(B("thinkfl/outputs/thinkfl-llama3-8b.jsonl"))
OPS, OPS_GT = load(B("opsagent/results/bundled__*.jsonl"), own_gt=True)
OPS_BY = {"telecom": [c for c in OPS if c.startswith("Telecom")], "bank": [c for c in OPS if c.startswith("Bank")], "market": [c for c in OPS if c.startswith("Market")], "aiops": []}

NAME = {"telecom": "Telecom", "bank": "Bank", "market": "Market", "aiops": "AIOps 2025"}
ep = lambda v: "- / -" if not v else f"{f1(v['C'])} / {f1(v['P'])}"   # Exact / Partial
def row(name, cells): return f"| {name} | " + " | ".join(cells) + " |"
def std(a, gt=None, missing="---"): return [ep(cell(a, BY[d], gt)) if any(c in a for c in BY[d]) else missing for d in DS]

out = ["| System | " + " | ".join(f"{NAME[d]} ({len(BY[d])}) Exact / Partial" for d in DS) + " |", "|---|" + "---|" * 4,
       "| *Statistical RCA* | | | | |",
       row("Nezha (§)", std(NEZHA)), row("KPIRoot", std(KPIROOT)), row("KPIRoot+", std(KPIROOTP)), row("Statistical EOB (NudgeRCA)", std(EOB, EOB_GT)),
       "| *w/o training* | | | | |",
       row("CoT (Qwen3-4B)", std(PRIOR)), row("ReAct (Qwen3-4B)", std(REACT)),
       row("RCA-Agent (GPT-5-mini) (‡)", std(GPT5M)[:3] + [ep(cell(GPT5M_A, BY["aiops"], GPT5M_GT))]),
       row("RCA-Agent (Solar Pro 4)", std(SOLAR4, SOLAR4_GT)),
       "| *Trained* | | | | |",
       row("OpsAgent-14B (†)", [ep(cell(OPS, OPS_BY[d], OPS_GT)) if OPS_BY[d] else "N/A" for d in DS]),
       row("ThinkFL-8B (‖)", std(THINKFL8)),
       row("NudgeRCA-4B", std(OURS)),
       "",
       "(§) Resource types and code regions are not mapped to benchmark fault types.",
       "(‖) Released checkpoints are trained on HipsterShop, the system of Market and AIOps 2025. ThinkFL-8B is based on Llama3-8B.",
       "(†) Result files released by the authors (Qwen2.5-14B-Instruct-1M) on their own split, which do not cover AIOps 2025.",
       "(‡) Public code (original prompt, up to 25 steps) run once per incident and rescored with our criteria."]
emit(out, HERE, "table_03")

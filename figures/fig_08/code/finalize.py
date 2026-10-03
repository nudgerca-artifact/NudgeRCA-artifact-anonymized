"""Renders the cases of one profiling-period setting into evaluation inputs with the paper's renderers (render_prompts_query.py --mode A;
Bank adds the trace and log-template blocks with build_bank_spec_render.py, Telecom the trace blocks with TRACE_TOPN=6 build_trace_prompts_telecom.py).
Row order and ground truth come from the paper's evaluation inputs (rendered-inputs/eval/<ds>.jsonl). Output: ../bundle/inputs/eval_<ds>_L<L>.jsonl,
and it prints the number of candidates and how often the first candidate is the root cause. Usage: python3 finalize.py <ds> <L>"""
import json, os, re, subprocess, sys, glob
ds, L = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__)); OR = f"{HERE}/pipeline/OpenRCA"; OUTD = f"{HERE}/../bundle/inputs"; os.makedirs(OUTD, exist_ok=True)
ART = os.path.normpath(os.path.join(HERE, "..", "..", ".."))   # the artifact root
ref = [json.loads(l) for l in open(f"{ART}/nudgerca/preprocessing/rendered-inputs/eval/{ds}.jsonl")]
env = {**os.environ, "CASES_SUFFIX": f"_L{L}"}
if ds == "market":   # the paper's Market renderer, evaluation incidents only
    sp = f"{OR}/output/split_eval_market_sweep.json"; json.dump({"eval": [r["case_id"] for r in ref]}, open(sp, "w"))
    menv = {**os.environ, "MARKET_SPLIT_FILE": sp, "MARKET_CASES_SUFFIX": f"_L{L}", "MARKET_OUT_SUFFIX": f"_L{L}"}
    subprocess.run([sys.executable, "build_market_spec_render.py", "eval"], cwd=OR, env=menv, check=True, capture_output=True)
    rows = {json.loads(l)["case_id"]: json.loads(l) for l in open(f"{OR}/output/gen_ready_market_spec_A_eval_L{L}.jsonl")}
else:
    subprocess.run([sys.executable, "render_prompts_query.py", "--dataset", ds, "--mode", "A"], cwd=OR, env=env, check=True, capture_output=True)
    rows = {json.loads(l)["case_id"]: json.loads(l) for l in open(f"{OR}/output/gen_ready_{ds}_L{L}_A.jsonl")}
if ds == "bank":
    tmp = f"{OR}/output/rendered_bank_eval_L{L}.jsonl"
    miss = [r["case_id"] for r in ref if r["case_id"] not in rows]; ref = [r for r in ref if r["case_id"] in rows]
    if miss: print("no candidate left (no samples before the window), skipped:", miss)
    open(tmp, "w").write("".join(json.dumps(rows[r["case_id"]], ensure_ascii=False) + "\n" for r in ref))
    subprocess.run([sys.executable, "build_bank_spec_render.py", tmp, f"{OR}/output/eval_bank_L{L}.jsonl"], cwd=OR, check=True, capture_output=True)
    fin = {json.loads(l)["case_id"]: json.loads(l) for l in open(f"{OR}/output/eval_bank_L{L}.jsonl")}
elif ds == "market":
    fin = dict(rows); miss = [r["case_id"] for r in ref if r["case_id"] not in fin]; ref = [r for r in ref if r["case_id"] in fin]
    if miss: print("no candidate left, skipped:", miss)
else:   # telecom: the trace block does not depend on the metric statistics; it is copied from the paper's prompt of the same incident
    fin = {}
    for r in ref:
        if r["case_id"] not in rows: continue
        x = dict(rows[r["case_id"]]); p = r["prompt"]; anchor = "## Answer in exactly this JSON"
        blk = p[p.index("## Trace summary"): p.index(anchor)] if "## Trace summary" in p else ""
        assert anchor in x["prompt"]; x["prompt"] = x["prompt"].replace(anchor, blk + anchor, 1); fin[r["case_id"]] = x
    miss = [r["case_id"] for r in ref if r["case_id"] not in fin]; ref = [r for r in ref if r["case_id"] in fin]
    if miss: print("no candidate left (no samples before the window), skipped:", miss)
V4 = os.environ.get("OPENRCA_CASE_DIR", "datasets/openrca-cases")   # per-incident case files of OpenRCA Bank and Telecom (ground truth)
if ds == "market": GT = {r["case_id"]: r["gt"]["components"] for r in ref if r["gt"]["components"]}
else:
    PFX, DDIR = {"bank": ("qb", "OpenRCA_Bank"), "telecom": ("qt", "OpenRCA_Telecom")}[ds]
    GT = {f"{PFX}_{int(os.path.basename(f)[:-5].rsplit('_',1)[1]):03d}": [json.load(open(f))["ground_truth"]["component"]] for f in glob.glob(f"{V4}/{DDIR}/*/*.json")}
sys.path.insert(0, f"{ART}/nudgerca/inference"); from score_openrca_corrected import comp_match
n = t1 = inl = k = 0
with open(f"{OUTD}/eval_{ds}_L{L}.jsonl", "w") as f:
    for r in ref:
        x = fin[r["case_id"]]; x["gt"] = r["gt"]; f.write(json.dumps(x, ensure_ascii=False) + "\n")
        top = re.findall(r"^### (\S+) \(", x["prompt"], re.M); g = GT.get(r["case_id"])
        if g: n += 1; t1 += bool(top) and any(comp_match(top[0], x) for x in g); inl += any(comp_match(c, x) for c in top for x in g); k += len(top)
print(f"{ds} L={L}: {len(ref)} prompts -> eval_{ds}_L{L}.jsonl | rank 1 = cause {100*t1/n:.0f} %, cause listed {100*inl/n:.0f} %, candidates {k/n:.1f}")

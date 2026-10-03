"""Latency summary of Figure fig:size. Reads the probes data/latency/l40s/<Size>_<trained|trained-int4>_<ds>.json (one L40S, one response per
incident sent one at a time, model loading excluded; written by code/latency_probe.py), keeps the first 10 evaluation incidents of each dataset
for every model, and writes data/latency/summary_l40s.json (4B keyed "trained" / "trained-int4", the other sizes "<Size>-trained" /
"<Size>-trained-int4"). Usage: python3 code/collect_latency.py"""
import json, os, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); L = os.path.join(HERE, "..", "data", "latency")
DS = ("telecom", "bank", "market"); SIZES = ("0.6B", "1.7B", "4B", "8B", "14B"); N = 10
recs = lambda p: json.load(open(p))["records"] if os.path.exists(p) else None
ids = {d: [r["case_id"] for r in recs(f"{L}/l40s/4B_trained_{d}.json")][:N] for d in DS}
models = {}
for S in SIZES:
    for cond in ("trained", "trained-int4"):
        key = cond if S == "4B" else f"{S}-{cond}"
        for d in DS:
            rr = recs(f"{L}/l40s/{S}_{cond}_{d}.json")
            if not rr: continue
            rr = [r for r in rr if r["case_id"] in ids[d]]
            if len(rr) != N: continue
            sec = sorted(r["sec"] for r in rr)
            models.setdefault(key, {})[d] = {"s_per_incident": round(st.mean(sec), 2), "median_s": round(st.median(sec), 2),
                                             "p95_s": round(sec[max(0, int(round(0.95 * N)) - 1)], 2),
                                             "tokens_per_s": round(st.mean(r["tok_per_s"] for r in rr), 1),
                                             "output_tokens": round(st.mean(r["out_tokens"] for r in rr)), "n": N}
for m in models.values():
    if all(d in m for d in DS): m["mean_three_datasets"] = {"s_per_incident": round(st.mean(m[d]["s_per_incident"] for d in DS), 2)}
note = ("Seconds per incident on one L40S: the first 10 evaluation incidents of each dataset (telecom, bank, market) sent one at a time "
        "(one response, temperature 0.6, up to 6,144 new tokens), model loading excluded (code/latency_probe.py). trained = the Qwen3 size with "
        "its adapter applied by vLLM (bf16, the evaluated NudgeRCA); trained-int4 = GPTQ W4A16 of the adapter merged in float32.")
json.dump({"note": note, "models": models}, open(f"{L}/summary_l40s.json", "w"), indent=1)
for k in sorted(models): print(f"{k:18s}", {d: models[k][d]["s_per_incident"] for d in DS if d in models[k]}, "mean", models[k].get("mean_three_datasets"))

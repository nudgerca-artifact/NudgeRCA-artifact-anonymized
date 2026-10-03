"""Single-request latency: send the first k incidents one at a time (n=1) and record wall time, output tokens and tokens per second.
Usage: python latency_probe.py --model <dir> --in <eval jsonl> --k 20 --max-model-len 24576 [--lora <adapter>] --out <json>"""
import argparse, json, time, subprocess, os
ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--k", type=int, default=20)
ap.add_argument("--max-model-len", type=int, default=24576); ap.add_argument("--max-new", type=int, default=6144); ap.add_argument("--lora"); ap.add_argument("--out", required=True); a = ap.parse_args()
from vllm import LLM, SamplingParams
kw = {"enable_lora": True, "max_lora_rank": 64} if a.lora else {}
llm = LLM(model=a.model, max_model_len=a.max_model_len, gpu_memory_utilization=0.9, **kw)
lr = None
if a.lora:
    from vllm.lora.request import LoRARequest; lr = LoRARequest("r", 1, a.lora)
rows = [json.loads(l) for l in open(a.inp)][: a.k]
sp = SamplingParams(n=1, max_tokens=a.max_new, temperature=0.6, top_p=0.95, top_k=20, seed=42)
recs = []
for r in rows:
    t0 = time.time()
    o = llm.chat([[{"role": "system", "content": r["system"]}, {"role": "user", "content": r["prompt"]}]], sp, chat_template_kwargs={"enable_thinking": True}, lora_request=lr)[0]
    dt = time.time() - t0; ntok = len(o.outputs[0].token_ids)
    recs.append({"case_id": r["case_id"], "sec": round(dt, 2), "out_tokens": ntok, "tok_per_s": round(ntok / dt, 1), "prompt_tokens": len(o.prompt_token_ids)})
mem = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
import statistics as st
summ = {"model": a.model, "lora": a.lora, "n": len(recs), "sec_mean": round(st.mean(r["sec"] for r in recs), 2), "sec_median": round(st.median(r["sec"] for r in recs), 2),
        "tok_per_s_mean": round(st.mean(r["tok_per_s"] for r in recs), 1), "out_tokens_mean": round(st.mean(r["out_tokens"] for r in recs)), "gpu_after": mem, "records": recs}
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True); json.dump(summ, open(a.out, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in summ.items() if k != "records"}, ensure_ascii=False))
try:
    import psutil
    for c in psutil.Process().children(recursive=True):
        try: c.kill()
        except Exception: pass
except Exception: pass
os._exit(0)

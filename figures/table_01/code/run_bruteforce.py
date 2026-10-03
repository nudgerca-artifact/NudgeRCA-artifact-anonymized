"""Stratified brute force over reasoning structures (Qwen3-4B, vLLM).

Matrix of eval cases × strata. Members within a stratum are injected in rotation by case index
(text clusters turned out not to be outcome-equivalence classes, so members rotate instead of
using a fixed representative).

Results: results/<TAG>/matrix/<uuid>__s<stratum>.json  (one per job; skipped if present = resume)
         results/<TAG>/baseline_eval/<uuid>.json
         _summary.json in each directory

Usage (g5.xlarge, 24GB):
  python3 run_bruteforce.py --dataset all --mode matrix --dry-run   # check without vLLM
  python3 run_bruteforce.py --dataset all --mode baseline           # no-injection baseline (377 calls)
  python3 run_bruteforce.py --dataset AIOps2025 --mode matrix       # strata × cases
  python3 run_bruteforce.py --dataset AIOps2025 --mode matrix --limit 2   # pilot (58 calls)
  python3 run_bruteforce.py --dataset AIOps2025 --mode matrix --strata 0,5,7
"""
import argparse, glob, json, os, re, sys, time

os.environ.setdefault("VLLM_USE_FLASHINFER_SAMPLER", "0")   # fallback for instances without nvcc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
from config import DATASETS, SPLIT, RESULTS, STRUCTS
from prompts import build_prompt_v4
from matchers import gt_rank

MODEL = os.environ.get("RB_MODEL", "Qwen/Qwen3-4B")
# Qwen3's recommended thinking-mode sampling (greedy runs into repetition loops)
SAMPLING = dict(temperature=0.6, top_p=0.95, top_k=20, min_p=0.0, seed=42)

INJECT_SYS_SUFFIX = (
    "\nAdditionally, ONE proven diagnostic reasoning structure from a DIFFERENT past case is provided "
    "after the data. Follow its PROCEDURE (the order and kind of reasoning steps) where it fits this "
    "case's evidence. Component/metric names inside the structure are from the OTHER case and are NOT "
    "the answer — REFERENCE ONLY, never copy them as your answer. Its 'pitfall' notes a misleading "
    "signal; watch for the same kind of trap in THIS case.")


MASK_RX = re.compile(r"\b(Tomcat|apache|Apache|IG|MG|Mysql|MySQL|Redis)\s?\d{2}\b")

def mask_names(t):
    return MASK_RX.sub("a component", str(t))


def struct_block(member, mask=False):
    if member.get("raw_block"):          # ablation: use the unstructured (plain-text) block as is
        return "\n" + str(member["raw_block"])
    L = ["\n=== REFERENCE diagnostic reasoning structure (from another past case; procedure only) ==="]
    pf = str(member.get("pitfall") or "")
    if pf:
        L.append(f"Pitfall to watch for: {mask_names(pf)[:160] if mask else pf[:160]}")
    for i, s in enumerate(member.get("steps") or [], 1):
        lab, inf = str(s.get("label")), str(s.get("inference") or "")
        if mask:
            lab, inf = mask_names(lab), mask_names(inf)
        L.append(f"Step {i} [{lab}]: {inf[:130]}" if inf else f"Step {i} [{lab}]")
    return "\n".join(L)


def parse_output(text):
    think = ""
    m = re.search(r"<think>(.*?)</think>", text, re.S)
    if m:
        think, rest = m.group(1).strip(), text[m.end():]
    else:
        parts = text.split("</think>")
        think, rest = (parts[0].strip(), parts[1]) if len(parts) > 1 else ("", text)
    names, ans = [], ""
    am = re.search(r"<answer>\s*(\{.*?\})\s*</answer>", rest, re.S)
    if am:
        ans = am.group(1)
        try:
            for e in json.loads(ans).get("rank_list", []):
                names.append(e.get("component") or e.get("metric") or "")
        except json.JSONDecodeError:
            pass
    if not names:   # fallback
        names = re.findall(r'"(?:component|metric)"\s*:\s*"([^"]+)"', rest)[:3]
    return think, ans, names


def load_cases(tag, split="eval", limit=0, uuids=None):
    """List of (global_idx, file), so rotation sampling uses full-list indices even on a subset."""
    files = sorted(glob.glob(os.path.join(SPLIT, tag, split, "*.json")))
    pairs = list(enumerate(files))
    if uuids:
        pairs = [(i, f) for i, f in pairs if os.path.splitext(os.path.basename(f))[0] in uuids]
    if limit:
        pairs = pairs[:limit]
    return pairs


def build_jobs(ds, cfg, args, strata, meta):
    """[(job_id, case_file, case_idx, stratum, member)]; stratum=None for baseline."""
    files = load_cases(cfg["out"], getattr(args, "split", "eval"), args.limit, getattr(args, "uuids", None))
    jobs = []
    for ci, f in files:
        u = os.path.splitext(os.path.basename(f))[0]
        if args.mode == "baseline":
            jobs.append((u, f, ci, None, None))
        elif args.mode == "pairs":
            membmap = {m["uuid"]: m for st in strata for m in st["members"]}
            seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else [SAMPLING["seed"]]
            for p in args.pairs:
                if p["uuid"] != u:
                    continue
                for sd in seeds:
                    # override: for component ablation; steps/pitfall/raw_block/sys_suffix overwrite the member
                    base = membmap.get(p["member_uuid"], {"uuid": p["member_uuid"], "component": "", "level": ""})
                    member = {**base, **p.get("override", {}), "_seed_abs": sd}
                    tag = p.get("tag", "")
                    jobs.append((f"{u}__p{p['member_uuid'][-8:]}{tag}__sd{sd}", f, ci, None, member))
        elif args.mode == "sc":
            # --sc-offset: when appending to an existing sc corpus, start sample numbers and seeds after it
            for k in range(args.sc_offset, args.sc_offset + args.n_samples):
                jobs.append((f"{u}__sc{k}", f, ci, None, {"_seed_offset": k}))
        else:
            for st in strata:
                if args.strata and st["stratum_id"] not in args.strata:
                    continue
                member = st["members"][ci % len(st["members"])]   # rotation sampling
                jobs.append((f"{u}__s{st['stratum_id']}", f, ci, st, member))
    return jobs


def run_dataset(ds, args, llm=None, tokenizer=None):
    cfg = DATASETS[ds]
    tag, level = cfg["out"], cfg["level"]
    strata = json.load(open(os.path.join(STRUCTS, "strata.json"))).get(tag, [])
    if getattr(args, "full", False) and args.mode == "matrix":
        members = sorted((m for st in strata for m in st["members"]), key=lambda m: m["uuid"])
        strata = [{"stratum_id": i, "members": [m]} for i, m in enumerate(members)]
    meta = json.load(open(os.path.join(STRUCTS, "case_levels.json"))).get(tag, {})
    root = args.results_root or RESULTS
    sub = {"matrix": ("matrix_full" if getattr(args, "full", False) else "matrix"),
           "baseline": "baseline_eval", "sc": "sc_eval", "pairs": "pairs"}[args.mode]
    if getattr(args, "mask_structs", False) and args.mode == "matrix":
        sub += "_masked"
    outdir = os.path.join(root, tag, sub)
    os.makedirs(outdir, exist_ok=True)

    jobs = build_jobs(ds, cfg, args, strata, meta)
    todo = [j for j in jobs if not os.path.exists(os.path.join(outdir, f"{j[0]}.json"))]
    print(f"[{ds}] mode={args.mode} strata={len(strata)} jobs={len(jobs)} todo={len(todo)} → {outdir}")

    if args.dry_run:
        for jid, f, ci, st, member in todo[:3]:
            case = json.load(open(f))
            sysp, usr, cands, _ = build_prompt_v4(case, ds, level)
            is_sc = member is not None and "_seed_offset" in member
            if member and not is_sc:
                usr = usr + "\n" + struct_block(member, getattr(args, "mask_structs", False))
            extra = (f" seed={SAMPLING['seed'] + member['_seed_offset']}" if is_sc
                     else f" member={member['uuid']}({member.get('level')})" if member else "")
            print(f"  {jid}: usr={len(usr)}chars cands={len(cands)} gt={case['ground_truth'].get('component')}{extra}")
        return

    from vllm import SamplingParams
    sp = SamplingParams(max_tokens=args.max_new, **SAMPLING)

    t_start = time.time(); n_done_tok = [0, 0]
    for i in range(0, len(todo), args.batch):
        chunk = todo[i:i + args.batch]
        msgs, metas = [], []
        for jid, f, ci, st, member in chunk:
            case = json.load(open(f))
            sysp, usr, cands, _ = build_prompt_v4(case, ds, level)
            seed_off = (member or {}).get("_seed_offset")
            if member and seed_off is None and (member.get("steps") or member.get("raw_block")):
                sysp = sysp + member.get("sys_suffix", INJECT_SYS_SUFFIX)
                usr = usr + "\n" + struct_block(member, getattr(args, "mask_structs", False))
            ids = tokenizer.apply_chat_template(
                [{"role": "system", "content": sysp}, {"role": "user", "content": usr}],
                tokenize=True, add_generation_prompt=True)
            if not isinstance(ids, list):
                ids = ids["input_ids"]
            if ids and isinstance(ids[0], list):
                ids = ids[0]
            n_in = len(ids)
            if n_in + args.max_new > args.max_model_len:
                json.dump({"uuid": case["uuid"], "job": jid,
                           "skipped": f"prompt {n_in}tok + max_new > {args.max_model_len}"},
                          open(os.path.join(outdir, f"{jid}.json"), "w"))
                continue
            msgs.append([{"role": "system", "content": sysp}, {"role": "user", "content": usr}])
            metas.append((jid, case, st, member, n_in))
        if not msgs:
            continue
        def _sp(member):
            s = dict(SAMPLING)
            if args.temp is not None:
                s["temperature"] = args.temp
            if member and "_seed_abs" in member:
                s["seed"] = member["_seed_abs"]
            else:
                s["seed"] = SAMPLING["seed"] + ((member or {}).get("_seed_offset", 0))
            extra = {"repetition_penalty": args.rep_penalty} if args.rep_penalty else {}
            return SamplingParams(max_tokens=args.max_new, **s, **extra)
        sps = [_sp(m[3]) for m in metas]
        _lr = None
        if os.environ.get("RB_LORA"):
            from vllm.lora.request import LoRARequest
            _lr = LoRARequest("rb_lora", 1, os.environ["RB_LORA"])
        outs = llm.chat(msgs, sps, chat_template_kwargs={"enable_thinking": True},
                        lora_request=_lr)
        for (jid, case, st, member, n_in), o in zip(metas, outs):
            gen = o.outputs[0]
            think, ans, names = parse_output(gen.text)
            gt = case["ground_truth"]
            rank = gt_rank(names, gt.get("component", ""), level)
            rec = {
                "uuid": case["uuid"], "job": jid, "dataset": ds, "level": level,
                "mode": args.mode, "model": MODEL,
                "sampling": {**SAMPLING, "temperature": args.temp if args.temp is not None else SAMPLING["temperature"],
                             "seed": (member or {}).get("_seed_abs", SAMPLING["seed"]),
                             "repetition_penalty": args.rep_penalty},
                "stratum_id": st["stratum_id"] if st else None,
                "sc_seed": SAMPLING["seed"] + member["_seed_offset"] if (member and "_seed_offset" in member) else None,
                "member_uuid": member.get("uuid") if member else None,
                "member_component": member.get("component") if member else None,
                "member_level": member.get("level") if member else None,
                "gt": gt, "pred": names, "answer_json": ans,
                "fr_rank": rank, "won": 1 if rank == 1 else 0,
                "case_meta": meta.get(case["uuid"], {}),
                "think": think,
                "n_prompt_tokens": n_in, "n_gen_tokens": len(gen.token_ids),
                "finish_reason": gen.finish_reason,
            }
            json.dump(rec, open(os.path.join(outdir, f"{jid}.json"), "w"), ensure_ascii=False)
            n_done_tok[0] += n_in; n_done_tok[1] += len(gen.token_ids)
        done = min(i + args.batch, len(todo))
        el = time.time() - t_start
        rate = done / el if el else 0
        eta = (len(todo) - done) / rate / 60 if rate else -1
        print(f"  [{ds}] {done}/{len(todo)}  ({rate*60:.1f} jobs/min, ETA {eta:.0f}min, "
              f"tok in/out {n_done_tok[0]/1e6:.1f}M/{n_done_tok[1]/1e6:.1f}M)", flush=True)

    # summary
    recs = []
    for f in glob.glob(os.path.join(outdir, "*.json")):
        if f.endswith("_summary.json"):
            continue
        try:
            recs.append(json.load(open(f)))
        except Exception:
            pass
    scored = [r for r in recs if "skipped" not in r]
    n = len(scored)
    summ = {"dataset": ds, "mode": args.mode, "n": n, "skipped": len(recs) - n,
            "top1": round(sum(1 for r in scored if r.get("fr_rank") == 1) / n, 4) if n else None,
            "top3": round(sum(1 for r in scored if r.get("fr_rank") and r["fr_rank"] <= 3) / n, 4) if n else None,
            "parse_fail": sum(1 for r in scored if not r.get("pred"))}
    json.dump(summ, open(os.path.join(outdir, "_summary.json"), "w"), indent=1)
    print(f"[{ds}] {args.mode} n={n} top1={summ['top1']} top3={summ['top3']} parse_fail={summ['parse_fail']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="config key or 'all'")
    ap.add_argument("--mode", choices=["baseline", "matrix", "sc", "pairs"], default="matrix")
    ap.add_argument("--pairs-file", default=None, help="pairs mode: JSON [{uuid, member_uuid}]")
    ap.add_argument("--seeds", default=None, help="pairs mode: comma-separated seed list")
    ap.add_argument("--temp", type=float, default=None, help="temperature override")
    ap.add_argument("--sc-offset", type=int, default=0, help="start offset for sc sample numbers and seeds")
    ap.add_argument("--uuids", default=None, help="run only these comma-separated case uuids (load_cases filter)")
    ap.add_argument("--rep-penalty", type=float, default=None, help="repetition_penalty (prevents loops at low temperature)")
    ap.add_argument("--n-samples", type=int, default=16, help="sc mode: samples per case (seed 42..42+N-1)")
    ap.add_argument("--limit", type=int, default=0, help="limit on the number of cases (pilot)")
    ap.add_argument("--strata", default=None, help="run only these comma-separated stratum_ids")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-new", type=int, default=8192)
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--gpu-mem-util", type=float, default=0.9)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--full", action="store_true", help="matrix: ignore clusters and inject every structure (|bank| per case)")
    ap.add_argument("--uuid-file", default=None, help="run only the case uuids in this file (one per line)")
    ap.add_argument("--split", default="eval", help="subfolder of _split60-40 (eval/extract)")
    ap.add_argument("--mask-structs", action="store_true", help="mask component names in the injected structure text (controls name leakage)")
    ap.add_argument("--results-root", default=None,
                    help="results root directory (default results/), to isolate each experiment, e.g. runs/<date>")
    args = ap.parse_args()
    args.strata = set(int(x) for x in args.strata.split(",")) if args.strata else None
    args.uuids = set(open(args.uuid_file).read().split()) if args.uuid_file else None
    args.pairs = json.load(open(args.pairs_file)) if args.pairs_file else None
    if args.mode == "pairs":
        assert args.pairs, "--pairs-file required"
        args.uuids = {p["uuid"] for p in args.pairs}

    targets = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]
    for ds in targets:
        assert ds in DATASETS, f"unknown dataset {ds}"

    llm = tokenizer = None
    if not args.dry_run:
        from vllm import LLM
        _lora = os.environ.get("RB_LORA")  # serve the LoRA adapter directly (no merge; mathematically identical)
        llm = LLM(model=MODEL, max_model_len=args.max_model_len,
                  gpu_memory_utilization=args.gpu_mem_util,
                  **({"enable_lora": True, "max_lora_rank": 64} if _lora else {}))
        tokenizer = llm.get_tokenizer()
    for ds in targets:
        run_dataset(ds, args, llm, tokenizer)


if __name__ == "__main__":
    main()

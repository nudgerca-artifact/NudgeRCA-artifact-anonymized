"""Build the judge input chunks for Table behavior (§3.3): yes/no questions judged independently by two reviewer models (Opus).

Chunk = 2 cases × 8 samples = 16 trajectories (case header once per case). Header = input summary (entity magnitude table, logs, traces, propagation),
GT, each trajectory's final answer (top-3 + rationale sentences), and the full raw reasoning.
Output: data/judge_inputs/chunk_XX.md, data/judge_inputs/index.json"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "common", "section3"))
import loaders as L
OUT = os.path.join(HERE, "data", "judge_inputs")
cases = L.load_v4_cases(); traj = L.load_v4_trajectories()
by_case = collections.defaultdict(list)
for t in traj: by_case[t["uuid"]].append(t)
uuids = sorted(by_case)

def short_kpi(k):
    k = k.replace("OSLinux-OSLinux_", "").replace("OSLinux-", "")
    return k
def case_header(u):
    c = cases[u]; m = c["metrics"]; sc = L.entity_scores_v4(c)
    L_ = [f"### CASE {u}", f"Ground truth (for your reference only): component={c['ground_truth']['component']}, fault={c['ground_truth']['fault_type']}",
          f"Candidate components in the prompt: {', '.join(m['all_entities'])}",
          "Anomalous metrics given to the model, grouped by entity, ordered by summed deviation (largest first). "
          "The prompt itself listed entities ALPHABETICALLY with severity bands (extreme/high/moderate), onset/peak times and value series."]
    kpis = collections.defaultdict(list)
    for a in m["anomalous"]: kpis[a["entity"]].append((float(a["max_z"]), short_kpi(a["kpi"]), a.get("shared_n", 1)))
    for e, s, mx, n in sc:
        ks = sorted(kpis[e], reverse=True)
        L_.append(f"- {e}: sum_z={s:.0f}, max_z={mx:.0f}, {n} signals: " + "; ".join(f"{k} (z={z:.0f}{' node-shared' if (sh or 1) > 1 else ''})" for z, k, sh in ks[:8]) + (" ..." if len(ks) > 8 else ""))
    lg = c.get("logs") or {}
    if lg.get("entries"):
        cnt = collections.Counter()
        for e in lg["entries"]: cnt[e.get("service") or e.get("pod") or "?"] += e.get("count", 1)
        L_.append("Error logs by service: " + ", ".join(f"{k}={v}" for k, v in cnt.most_common()))
    tr = c.get("traces") or {}
    if tr.get("service_summary"):
        slow = [f"{s['service']} (x{s['slow_ratio_vs_peers']})" for s in tr["service_summary"] if (s.get("slow_ratio_vs_peers") or 0) >= 1.5]
        L_.append("Trace summary services: " + ", ".join(s["service"] for s in tr["service_summary"]) + (" | slow vs peers: " + ", ".join(slow) if slow else ""))
    prop = m.get("propagation") or {}
    if prop:
        L_.append("Propagation section (entity: anomalous upstream callers / anomalous downstream deps):")
        for e, rel in prop.items():
            L_.append(f"  - {e}: up=[{', '.join(rel.get('upstream_anomalous', [])) or 'none'}] down=[{', '.join(rel.get('downstream_anomalous', [])) or 'none'}]")
    return "\n".join(L_)

def traj_block(t):
    try:
        rl = json.loads(t["answer_json"])["rank_list"]
        ans = "\n".join(f"  {i+1}. {r.get('component')}: {r.get('description')}" for i, r in enumerate(rl[:3]))
    except Exception:
        ans = "  " + ", ".join(t["pred"])
    return f"#### TRAJECTORY job={t['job']} (correct={'yes' if t['won'] else 'no'})\nFINAL ANSWER (ranked):\n{ans}\nREASONING (verbatim):\n<<<\n{t['think']}\n>>>\n"

if __name__ == "__main__":
    index = []
    for i in range(0, len(uuids), 2):
        chunk = uuids[i:i + 2]; cid = f"chunk_{i//2:02d}"
        parts = []
        for u in chunk:
            parts.append(case_header(u)); parts.extend(traj_block(t) for t in sorted(by_case[u], key=lambda t: t["sample"]))
        open(os.path.join(OUT, cid + ".md"), "w").write("\n\n".join(parts))
        index.append(dict(chunk=cid, cases=chunk, jobs=[t["job"] for u in chunk for t in sorted(by_case[u], key=lambda t: t["sample"])]))
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    sizes = [os.path.getsize(os.path.join(OUT, r["chunk"] + ".md")) for r in index]
    print(f"{len(index)} chunks, {sum(len(r['jobs']) for r in index)} jobs, chunk size chars min/med/max = {min(sizes)}/{sorted(sizes)[len(sizes)//2]}/{max(sizes)}")

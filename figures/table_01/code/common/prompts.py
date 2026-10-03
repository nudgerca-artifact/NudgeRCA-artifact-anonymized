"""Baseline prompt for observing pitfalls (based on the earlier prompt builder, with the coaching removed).

The original `## Anomaly propagation` section mixes two layers of a different nature:
  - data: the upstream_anomalous/downstream_anomalous lists, a preprocessing product (observed information)
  - coaching: Note("check the propagation direction ... do not decide by deviation magnitude
    alone"), a reasoning instruction = the intervention we study, statically baked into the prompt

Principle: **keep the data, remove only the coaching** (default propagation="data").
  - Removing the data too would make "failed for lack of information" indistinguishable from
    "saw the information and ignored it" (the real pitfall). Earlier evaluation runs also observed
    all failures with the data included.
  - baseline and ours (intervention) must get the same input; adding information only to ours would
    measure an information effect, not the intervention effect. The coaching Note is used only as a
    separate arm (static coaching baseline).
The system prompt is likewise a neutral SYS_BASE-level instruction without propagation framing
("distinguish ROOT CAUSE from PROPAGATION"). |PEAK|, [node-shared xN], [slow xN vs peers] and the
Component Graph are data representations, so they stay.

propagation argument:
  "data" (default): only the data lists of the section; common input for taxonomy collection, baseline, ours
  "full"          : data + coaching Note; static coaching baseline arm (same as the original eval)
  "none"          : whole section excluded; for the information-presence ablation
"""
import glob
import json
import os

import numpy as np
from topology import get_graph_text

# ── System prompt: neutral (based on SYS_BASE of the earlier evaluation script). The output schema is
#    shared by all experiments/arms: component rank_list + a one-line description per item. No upstream
#    field: it would push the model into forced propagation reasoning. Scoring looks only at component.
#    Note: the pitfall analysis classifies the whole <think> reasoning trace with an LLM-as-judge, not
#    this description; the description only unifies the output format ──
SYS_BASELINE_COMPONENT = (
    "You are an expert SRE doing Root Cause Analysis on a cloud/microservice/database failure. "
    "You are given anomalous metrics (|PEAK|=max deviation), logs, a trace summary, propagation, and a "
    "component graph. Identify the TOP 3 most likely root-cause components, ranked. Names verbatim from "
    "the candidate list. For each, give a one-sentence description of why you ranked it there.\n"
    "Output ONLY this JSON in <answer></answer>:\n"
    '<answer>{"rank_list": [{"component": "<name>", "description": "<why>"}, '
    '{"component": "<2nd>", "description": "<why>"}, {"component": "<3rd>", "description": "<why>"}]}</answer>'
)
SYS_BASELINE_METRIC = (
    "You are an expert SRE doing Root Cause Analysis on a database system failure. "
    "You are given anomalous metric time series (|PEAK|=max deviation). Identify the TOP 3 most "
    "likely root-cause metrics, ranked. Names verbatim from the candidate list. For each, give a "
    "one-sentence description of why you ranked it there.\n"
    "Output ONLY this JSON in <answer></answer>:\n"
    '<answer>{"rank_list": [{"metric": "<name>", "description": "<why>"}, '
    '{"metric": "<2nd>", "description": "<why>"}, {"metric": "<3rd>", "description": "<why>"}]}</answer>'
)


def _peak_values(a, max_vals=40):
    """Returns: (value series string, actual peak timestamp or None). Same as the original."""
    vals = a.get("values", []) or []
    if not vals:
        return "", None
    mu = a.get("mu", 0.0); sig = a.get("sigma", 1.0) or 1.0
    z = [abs((v - mu) / sig) for v in vals]
    pk = int(np.argmax(z))
    ts = a.get("timestamps", []) or []
    peak_ts = int(ts[pk]) if pk < len(ts) else None
    vals = vals[:max_vals]
    s = ", ".join((f"|PEAK|{v}" if i == pk else f"{v}") for i, v in enumerate(vals))
    return s, peak_ts


def build_baseline_prompt(case, dataset, level="component", propagation="data", include_z=True):
    """case JSON → (system_prompt, user_prompt, candidates, answer_key).

    propagation: "data" (default, lists only) / "full" (+coaching Note, same as original) / "none" (section excluded)
    include_z=False: drop the z values from anomaly lines (anchoring ablation: blocks the magnitude
                     comparison cue, keeps the peak time and series values)
    """
    assert propagation in ("data", "full", "none")
    m = case["metrics"]
    t0 = None
    if onset_style == "relative":
        onsets = [a["onset_ts"] for a in m.get("anomalous", []) if a.get("onset_ts")]
        t0 = min(onsets) if onsets else None
    win = case.get("window", {})
    notation = (" onset@+Ns / peak@+Ns = N seconds after the EARLIEST anomaly onset in this incident"
                " (smaller = started earlier)." if t0 is not None else "")
    L = [f"## Failure window: {win.get('start')} ~ {win.get('end')}{notation and chr(10) + '## Notation:' + notation}",
         f"## Anomalous metrics (k-sigma, time series; |PEAK| = max deviation) — {m.get('anomalous_count', 0)} signals"]
    _anoms = m.get("anomalous", [])
    if os.environ.get("RB_SORT_ONSET") == "1":
        # Notation-level change: sort the anomalous-metric table by onset time; content unchanged, order only.
        # Rationale: in cases whose answer is a backend, the answer signals (median 3) come first yet are
        # buried alphabetically among the Tomcat noise (median 12) (measured discriminability).
        _anoms = sorted(_anoms, key=lambda a: (a.get("onset_ts") is None,
                                               int(a.get("onset_ts") or 0)))
    for a in _anoms:
        sh = a.get("shared_n", 1) or 1
        tag = f" [node-shared x{sh}]" if sh > 1 else ""
        sv, pts = _peak_values(a)
        pt = f" peak@{pts}" if pts is not None else ""
        if include_z:
            L.append(f"- {a['entity']} | {a['kpi']} (z={a.get('max_z')}{pt}){tag}: [{sv}]")
        else:
            L.append(f"- {a['entity']} | {a['kpi']} ({pt.strip() if pt else 'anomalous'}){tag}: [{sv}]")

    lg = case.get("logs", {}) or {}
    _lv2 = _logs_v2(case) if os.environ.get("RB_LOGS_V2") == "1" else None
    if _lv2 is not None:
        L.extend(_render_logs_v2(_lv2))
    elif lg.get("entries"):
        by_svc = {}
        for e in lg["entries"]:
            s = e.get("service", "") or e.get("pod", "")
            d = by_svc.setdefault(s, {"count": 0, "msg": str(e.get("message", "")).strip()})
            d["count"] += e.get("count", 1)
        L.append(f"\n## Error logs by service (total {lg.get('total_in_window')}, errors {lg.get('error_count')})")
        for s, d in sorted(by_svc.items(), key=lambda x: -x[1]["count"]):
            L.append(f"- {s}: {d['count']} errors — {d['msg'][:400]}")

    tr = case.get("traces", {}) or {}
    if tr.get("service_summary"):
        L.append(f"\n## Trace summary (total spans {tr.get('total_spans')}, error spans {tr.get('error_spans')})")
        if os.environ.get("RB_LOGS_V2") == "1":
            _insts = ", ".join(sorted({str(x.get("service")) for x in tr["service_summary"]}))
            L.append(f"(Only these services are trace-instrumented: {_insts}. "
                     "Mysql, Redis and apache produce NO spans — absence of trace data there "
                     "is NOT evidence of health.)")
        for s in tr["service_summary"]:
            sr = s.get("slow_ratio_vs_peers")
            srtxt = f" [slow x{sr} vs peers]" if sr and sr >= 1.5 else ""
            lr = s.get("latency_ratio")
            lrtxt = (f" latency x{lr} vs own baseline" if isinstance(lr, (int, float)) and lr
                     and os.environ.get("RB_LOGS_V2") == "1" else "")
            L.append(f"- {s.get('service')}: spans={s.get('span_count')} err={s.get('error_count')} "
                     f"avg={s.get('avg_duration_ms')}ms p95={s.get('p95_duration_ms')}ms{lrtxt}{srtxt}")

    # propagation data (a preprocessing product) is included by default, the coaching Note only in "full" (original [v3-causal])
    prop = m.get("propagation") or {}
    if prop and propagation != "none":
        L.append("\n## Anomaly propagation (among anomalous components, from the call graph)")
        for ent, rel in prop.items():
            up = ", ".join(rel.get("upstream_anomalous", [])) or "none"
            dn = ", ".join(rel.get("downstream_anomalous", [])) or "none"
            L.append(f"- {ent}: anomalous upstream callers=[{up}] ; anomalous downstream deps=[{dn}]")
        if propagation == "full":
            L.append("Note: an anomaly can be a SYMPTOM propagated from a neighbor. For each candidate, check the "
                     "propagation direction (which side failed first / shows errors) before concluding it is the root "
                     "cause — do not decide by deviation magnitude alone.")

    if level == "metric":
        cands = sorted({a["kpi"] for a in m.get("anomalous", [])})
        L.append("\n## Candidate metrics (pick the TOP 3 most likely, verbatim):")
        L.append(", ".join(cands))
        return SYS_BASELINE_METRIC, "\n".join(L), cands, "metric"
    else:
        cands = list(m.get("all_entities", []))
        graph = get_graph_text(dataset, cands)
        if graph:
            L.append("\n" + graph)
        L.append("\n## Candidate components (pick the TOP 3 most likely, verbatim):")
        L.append(", ".join(cands))
        return SYS_BASELINE_COMPONENT, "\n".join(L), cands, "component"


# ============================================================
# [v4 representation] severity bands + explicit onset@ + no ordering hint + compressed propagation
#   Design rationale:
#   - raw z values carry no information once saturated at the cap (30) yet strongly invite sorting -> replaced by ordinal bands
#   - sorting the list by z descending is itself a ranking hint -> entities in alphabetical order (explicitly meaningless order)
#   - explicit onset@ (first threshold crossing, v4 field): information for temporal discrimination (peak@ is the deepest point)
#   - propagation: merge entities with the same relation signature (lossless compression, against the AIOps blow-up)
#   - series >40: bucket means instead of head truncation (|PEAK| marker kept)
# ============================================================

SYS_V4_COMPONENT = (
    "You are an expert SRE doing Root Cause Analysis on a cloud/microservice/database failure. "
    "You are given anomalous metrics (severity = detection band; onset@ = when the anomaly first "
    "crossed the detection threshold; |PEAK| = strongest point in the series), logs, a trace "
    "summary, propagation, and a component graph. Identify the TOP 3 most likely root-cause "
    "components, ranked. Names verbatim from the candidate list. For each, give a one-sentence "
    "description of why you ranked it there.\n"
    "Output ONLY this JSON in <answer></answer>:\n"
    '<answer>{"rank_list": [{"component": "<name>", "description": "<why>"}, '
    '{"component": "<2nd>", "description": "<why>"}, {"component": "<3rd>", "description": "<why>"}]}</answer>'
)
SYS_V4_METRIC = (
    "You are an expert SRE doing Root Cause Analysis on a database system failure. "
    "You are given anomalous metric time series (severity = detection band; onset@ = first "
    "threshold crossing; |PEAK| = strongest point). Identify the TOP 3 most likely root-cause "
    "metrics, ranked. Names verbatim from the candidate list. For each, give a one-sentence "
    "description of why you ranked it there.\n"
    "Output ONLY this JSON in <answer></answer>:\n"
    '<answer>{"rank_list": [{"metric": "<name>", "description": "<why>"}, '
    '{"metric": "<2nd>", "description": "<why>"}, {"metric": "<3rd>", "description": "<why>"}]}</answer>'
)


def _severity(z):
    if z is None:
        return "moderate"
    return "extreme" if z >= 10 else ("high" if z >= 5 else "moderate")


def _series_v4(a, max_vals=40):
    """Series string (bucket downsampling, |PEAK| kept) + peak_ts."""
    vals = a.get("values", []) or []
    if not vals:
        return "", None
    mu = a.get("mu", 0.0); sig = a.get("sigma", 1.0) or 1.0
    z = [abs((v - mu) / sig) for v in vals]
    pk = int(np.argmax(z))
    ts = a.get("timestamps", []) or []
    peak_ts = int(ts[pk]) if pk < len(ts) else None
    if len(vals) > max_vals:                      # bucket means (no head truncation)
        import math
        bsz = math.ceil(len(vals) / max_vals)
        bucketed = [sum(vals[i:i+bsz]) / len(vals[i:i+bsz]) for i in range(0, len(vals), bsz)]
        pk_b = pk // bsz
        vals, pk = bucketed, pk_b
    s = ", ".join((f"|PEAK|{round(v, 4)}" if i == pk else f"{round(v, 4)}") for i, v in enumerate(vals))
    return s, peak_ts


def _render_propagation_v4(prop):
    """Merge entities with the same (upstream, downstream) signature into one line (lossless compression)."""
    sig2ents = {}
    for ent, rel in prop.items():
        key = (tuple(sorted(rel.get("upstream_anomalous", []))),
               tuple(sorted(rel.get("downstream_anomalous", []))))
        sig2ents.setdefault(key, []).append(ent)
    L = ["\n## Anomaly propagation (among anomalous components, from the call graph)"]
    for (up, dn), ents in sorted(sig2ents.items(), key=lambda x: sorted(x[1])[0]):
        L.append(f"- {', '.join(sorted(ents))}: anomalous upstream callers=[{', '.join(up) or 'none'}] ; "
                 f"anomalous downstream deps=[{', '.join(dn) or 'none'}]")
    return L



def _sys_with_hint(sysp):
    """RB_DECIDE_HINT=1: elicitation probe (latent level): one line asking to compare discriminating evidence before deciding.
    Not a procedure injection: one behavioral sentence; the model generates the content itself."""
    if os.environ.get("RB_DECIDE_HINT") == "1":
        return sysp + ("\nBefore giving the final ranking, explicitly compare the top "
                       "candidate components against each other using concrete evidence that "
                       "discriminates them (cite specific metric values, onset times, span/log "
                       "signals), then decide.")
    return sysp


# ============================================================
# [RB_NARRATIVE=1] narrative rendering along a call-graph walk
# Motivation (measured): anomalous-metric lines per case are 11.6 for Tomcat vs 4.7-5.7 for the rest, logs exist
# only for Tomcat, trace spans only for IG/Tomcat/MG -> in 73% of runs the model's top answer family is in the
# top 1-2 by line count. That is, volume itself pulls the answer. This renderer gives **every candidate the same
# slot** and describes them in call-graph order: at most K anomalies per component (family-specific KPIs first ->
# earliest onset), with logs and traces folded into that component's line. The selection rule is deterministic
# and does not use the ground truth (family specificity is a corpus telemetry statistic).
# ============================================================
_KPI_STATS = None


def _kpi_stats():
    global _KPI_STATS
    if _KPI_STATS is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "kpi_family_stats_bank.json")) as fh:
                _KPI_STATS = json.load(fh)
        except Exception:
            _KPI_STATS = {}
    return _KPI_STATS


# The call-graph walk order and relation sentences are generated from the topology file.
_WALK_CACHE = {}


def _build_walk(dataset):
    """topology.txt -> [(group, [instances], relation sentence)] (topological order, upstream -> downstream)."""
    if dataset in _WALK_CACHE:
        return _WALK_CACHE[dataset]
    import re as _re
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "evaluation", "dataset-topology-graph",
                        dataset.replace("/", "_"), "topology.txt")
    edges = []
    try:
        for line in open(path):
            m = _re.search(r'"([^"]+)"\s+calls\s+"([^"]+)"', line)
            if m:
                edges.append((m.group(1), m.group(2)))
    except Exception:
        return []
    inst = {}          # instance -> group (child name starts with the parent name = Instantiate)
    for a, b in edges:
        if b != a and b.startswith(a):
            inst[b] = a
    groups = {}        # group -> list of instances
    for b, a in inst.items():
        groups.setdefault(a, []).append(b)
    gedges = set()     # calls between groups (instances folded into their group)
    for a, b in edges:
        if inst.get(b) == a:
            continue
        ga, gb = inst.get(a, a), inst.get(b, b)
        if ga != gb:
            gedges.add((ga, gb))
    # topological sort (starting from in-degree 0)
    nodes = {g for g in groups} | {x for e in gedges for x in e}
    indeg = {g: sum(1 for a, b in gedges if b == g) for g in nodes}
    order, ready = [], sorted(g for g in nodes if indeg[g] == 0)
    seen = set()
    while ready:
        g = ready.pop(0)
        if g in seen:
            continue
        seen.add(g); order.append(g)
        for a, b in sorted(gedges):
            if a == g:
                indeg[b] -= 1
                if indeg[b] <= 0 and b not in seen:
                    ready.append(b)
    order += sorted(n for n in nodes if n not in seen)
    walk = []
    for g in order:
        insts = sorted(groups.get(g, []))
        if not insts:
            continue                      # skip abstract nodes without instances (OSB etc.)
        callers = sorted({a for a, b in gedges if b == g})
        callees = sorted({b for a, b in gedges if a == g})
        parts = [f"{g} consists of {', '.join(insts)}"]
        if callers:
            parts.append(f"is called by {', '.join(callers)}")
        parts.append(f"calls {', '.join(callees)}" if callees
                     else "calls no other service group (leaf of the call graph)")
        walk.append((g, insts, ". ".join([parts[0], " and ".join(parts[1:])]) + "."))
    _WALK_CACHE[dataset] = walk
    return walk


def _entry_for(entity, case, t0, k):
    """Up to k anomaly summaries of one component + one line of logs/traces. Selection rule:
    family-specific KPIs first (corpus statistic conc>=0.8) -> earliest onset -> largest deviation."""
    st = _kpi_stats()
    anos = [a for a in case["metrics"].get("anomalous", []) if a.get("entity") == entity]

    def rank(a):
        s = st.get(a.get("kpi"), {})
        distinctive = 0 if (s.get("conc", 0) >= 0.8 and s.get("n", 0) >= 5) else 1
        onset = a.get("onset_ts")
        return (distinctive, onset is None, int(onset or 0), -float(a.get("max_z") or 0))

    picked = sorted(anos, key=rank)[:k]
    bits = []
    for a in picked:
        sv, pts = _series_v4(a)
        onset = a.get("onset_ts")
        when = (f"onset@+{onset - t0}s" if (t0 is not None and onset is not None)
                else (f"onset@{onset}" if onset is not None else "onset unknown"))
        peak = ""
        try:
            vals = [float(x) for x in a.get("values", []) if x is not None]
            if vals:
                peak = f", peak {max(vals, key=lambda v: abs(v - float(a.get('mu') or 0)))}"
        except Exception:
            pass
        s = st.get(a.get("kpi"), {})
        mark = " [distinctive to this service type]" if (
            s.get("conc", 0) >= 0.8 and s.get("n", 0) >= 5) else ""
        bits.append(f"{a.get('kpi')} ({when}{peak}){mark}")
    n_more = max(len(anos) - len(picked), 0)
    txt = "; ".join(bits) if bits else "no anomalous metric"
    if n_more:
        txt += f"; (+{n_more} more anomalous metrics of the same kinds)"
    lv = _logs_v2(case) if os.environ.get("RB_LOGS_V2") == "1" else None
    if lv is not None:
        he = (lv.get("http_errors") or {}).get(entity)
        if he:
            txt += f"; HTTP errors: {he['count']} (first @+{he['first_at_s']}s)"
        ce = (lv.get("catalina_events") or {}).get(entity)
        if ce and ce.get("count"):
            txt += f"; server restart/exception lines: {ce['count']}"
    else:
        lg = case.get("logs", {}) or {}
        lc = sum(e.get("count", 1) for e in (lg.get("entries") or [])
                 if (e.get("service") or e.get("pod")) == entity)
        if lc:
            txt += f"; error logs: {lc}"
    tr = {s.get("service"): s for s in (case.get("traces", {}) or {}).get("service_summary", [])}
    ts = tr.get(entity)
    if ts:
        sr = ts.get("slow_ratio_vs_peers")
        lr = ts.get("latency_ratio")
        base = (f"; trace latency x{lr} vs own baseline (p95={ts.get('p95_duration_ms')}ms)"
                if isinstance(lr, (int, float)) and lr else
                f"; trace p95={ts.get('p95_duration_ms')}ms")
        txt += base + (f" [slow x{sr} vs peers]" if sr and sr >= 1.5 else "")
    return txt



# [RB_LOGS_V2=1] log v2 sidecar (see build_logs_v2.py): shows HTTP 5xx and catalina restarts and the log rate against the
# baseline, leaving out routine GC logs. Without a sidecar the previous log section is used.
def _logs_v2(case, cache={}):
    u = case.get("uuid")
    if u not in cache:
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                         "preprocess-v4/_split60-40/OpenRCA_Bank/logs_v2", f"{u}.json")
        try:
            cache[u] = json.load(open(f))
        except Exception:
            cache[u] = None
    return cache[u]


def _render_logs_v2(lv):
    cov = ", ".join(lv.get("coverage") or []) or "Tomcat, apache"
    L = [f"\n## Service logs (log-emitting services in this system: {cov};"
         " all other components emit NO logs — absence of logs is NOT evidence of health)"]
    he = lv.get("http_errors") or {}
    if he:
        for s_, x in sorted(he.items()):
            st = ", ".join(f"{k}x{v}" for k, v in sorted(x.get("statuses", {}).items()))
            L.append(f"- HTTP errors at {s_}: {x['count']} ({st}), first @+{x['first_at_s']}s")
    else:
        L.append("- HTTP errors (non-200 responses): none observed in this window")
    ce = lv.get("catalina_events") or {}
    for s_, x in sorted(ce.items()):
        if x.get("count"):
            L.append(f"- Server lifecycle events at {s_}: {x['count']} lines"
                     " (restart/exception burst — abnormal)")
    ratios = {s_: x.get("ratio") for s_, x in (lv.get("log_rate") or {}).items()
              if x.get("ratio") is not None}
    dev = {s_: r for s_, r in ratios.items() if r and (r >= 2.0 or r <= 0.5)}
    # Measured: deviations occur on a median of 6/8 services at once per case (global load), and "highest
    # log rate = answer family" holds in only 26% (uninformative) -> fold a broad rise into one line; list only when 1-2 stand out.
    if dev and len(dev) <= 2:
        L.append("- Log volume vs each service's own baseline: "
                 + ", ".join(f"{s_} x{r}" for s_, r in sorted(dev.items()))
                 + " (all other services within normal range)")
    elif dev:
        import statistics as _st
        _md = _st.median(sorted(dev.values()))
        _dirw = "elevated" if _md > 1 else "suppressed (request throughput drop)"
        L.append(f"- Log volume is {_dirw} broadly across {len(dev)} of {len(ratios)}"
                 f" log-emitting services (median x{_md:.1f} of each service's own baseline)"
                 " — a system-wide effect; log volume does NOT identify the faulty component.")
    else:
        L.append("- Log volume: every service is within its normal range")
    L.append("- Note: Tomcat GC lines (e.g. 'Allocation Failure') occur at a steady background"
             " rate in ALL Tomcat instances at all times; their presence alone is NOT evidence"
             " that a Tomcat instance is the root cause.")
    return L


# [RB_METRICS_V2=1] metric v2 sidecar (see build_metrics_v2.py):
# v4 anomaly detection uses the "span just before the fault" as baseline, so background metrics (constant
# fluctuation) pass as anomalies. The sidecar holds each series' normal-period firing rate against its own
# full-period baseline (fault windows excluded). v1 rendering rule: keep row order and content as is
# (separated from ordering effects) and only add a baseline-check note per row.
# Rare signals v4 missed (z>=3 vs the full-period baseline, normal firing rate <2%) are appended in a separate section.
_MV2_INFO = {}


def _metrics_v2(case, cache={}):
    u = case.get("uuid")
    if u not in cache:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "preprocess-v4/_split60-40")
        f = os.path.join(base, "OpenRCA_Bank/metrics_v2", f"{u}.json")
        info = {"bank": True, "meta": None}
        if not os.path.exists(f):
            # Datasets other than Bank: find the sidecar folder by uuid. If the folder has _dataset_meta.json
            # (number of normal windows), it is added to the rendered text so that "0.00%" on datasets with
            # few windows (Nezha ~140, Eadro_TT ~40) is not over-trusted. The Bank rendering stays byte-identical.
            hits = sorted(glob.glob(os.path.join(base, "*", "metrics_v2", f"{u}.json")))
            if hits:
                f = hits[0]
                info["bank"] = False
                try:
                    info["meta"] = json.load(open(os.path.join(os.path.dirname(f), "_dataset_meta.json")))
                except Exception:
                    info["meta"] = None
        try:
            cache[u] = json.load(open(f))
        except Exception:
            cache[u] = None
        _MV2_INFO[u] = info
    return cache[u]


def _mv2_tier(bg, nwin=None):
    p = (bg or 0.0) * 100
    if p <= 0.5:
        word = "very rare for this series"
    elif p <= 2:
        word = "rare for this series"
    elif p <= 10:
        word = "occasional for this series"
    else:
        word = "frequent — background-level"
    if nwin:
        return f"{p:.2f}% of {nwin} normal windows — {word}"
    return f"{p:.2f}% of normal windows — {word}"


def _render_narrative_v4(case, t0, k=2, dataset="OpenRCA/Bank"):
    L = ["## Incident walk along the call graph "
         "(every component is listed with the SAME amount of detail; "
         "the number of listed signals does NOT indicate importance)"]
    for _, insts, sentence in _build_walk(dataset):
        L.append(sentence)
        for e in insts:
            L.append(f"  - {e}: {_entry_for(e, case, t0, k)}")
    return L


def build_prompt_v4(case, dataset, level="component", propagation="data", onset_style=None):
    """onset_style: None/"epoch" = previous notation (default), "relative" = seconds relative to the first anomaly in the incident.
    Can also be set with env RB_ONSET_STYLE (the argument takes precedence). Same information and order; only readability changes."""
    onset_style = onset_style or os.environ.get("RB_ONSET_STYLE", "epoch")
    """v4 representation prompt. Returns (system_prompt, user_prompt, candidates, answer_key)."""
    assert propagation in ("data", "full", "none")
    m = case["metrics"]
    t0 = None
    if onset_style == "relative":
        onsets = [a["onset_ts"] for a in m.get("anomalous", []) if a.get("onset_ts")]
        t0 = min(onsets) if onsets else None
    win = case.get("window", {})
    notation = (" onset@+Ns / peak@+Ns = N seconds after the EARLIEST anomaly onset in this incident"
                " (smaller = started earlier)." if t0 is not None else "")
    if os.environ.get("RB_NARRATIVE") == "1":
        # narrative rendering: metrics, logs and traces are folded into the same per-component slot.
        _k = int(os.environ.get("RB_NARRATIVE_K", "2"))
        L = [f"## Failure window: {win.get('start')} ~ {win.get('end')}"
             + (chr(10) + "## Notation:" + notation if notation else "")]
        L.extend(_render_narrative_v4(case, t0, _k, dataset))
        prop = m.get("propagation") or {}
        if prop and propagation != "none":
            L.extend(_render_propagation_v4(prop))
        cands = list(m.get("all_entities", []))
        if os.environ.get("RB_CANDS_POD") == "1":
            keep = {e for _, insts, _ in _build_walk(dataset) for e in insts}
            cands = [c for c in cands if c in keep]
        graph = get_graph_text(dataset, cands)
        if graph:
            L.append("\n" + graph)
        L.append("\n## Candidate components (pick the TOP 3 most likely, verbatim):")
        L.append(", ".join(cands))
        return _sys_with_hint(SYS_V4_COMPONENT), "\n".join(L), cands, "component"

    L = [f"## Failure window: {win.get('start')} ~ {win.get('end')}{notation and chr(10) + '## Notation:' + notation}",
         f"## Anomalous metrics — {m.get('anomalous_count', 0)} signals "
         + ("(sorted by onset time, earliest first; "
            if os.environ.get("RB_SORT_ONSET") == "1" else
            "(entity blocks sorted by each entity's earliest onset; "
            if os.environ.get("RB_SORT_ONSET") == "2" else
            "(entities in alphabetical order — ordering carries NO meaning; ")
         + "severity: extreme/high/moderate = detection band)"]
    _mv2 = _metrics_v2(case) if os.environ.get("RB_METRICS_V2") == "1" else None
    _mv2_idx = None
    _mv2_bank, _mv2_nwin = True, None
    if _mv2 is not None:
        _nfo = _MV2_INFO.get(case.get("uuid")) or {}
        _mv2_bank = _nfo.get("bank", True)
        _mv2_nwin = (_nfo.get("meta") or {}).get("n_windows")
        _bl = "10-day" if _mv2_bank else "full-period"
        if _mv2_bank:
            _span = "the full 10-day telemetry"
        elif _mv2_nwin:
            _span = f"the full telemetry ({_mv2_nwin} normal 10-min windows observed)"
        else:
            _span = "the full observed telemetry"
        L.append(f"(baseline-check annotations compare each signal to ITS OWN series over {_span}"
                 " with fault windows excluded; 'N% of normal windows' = how often"
                 " that series crosses the same z threshold during NORMAL operation. Lower % = more"
                 " unusual now. Signals marked background-level fire routinely even without faults.)")
        _mv2_idx = {(str(e), str(s.get("kpi"))): s for e, v in _mv2.items() for s in v}
    _sort_mode = os.environ.get("RB_SORT_ONSET")
    if _sort_mode == "1":
        # global interleaved onset sort (A/B: backend opened first, Redis 0->6, but Tomcat -18)
        anos = sorted(m.get("anomalous", []),
                      key=lambda a: (a.get("onset_ts") is None, int(a.get("onset_ts") or 0),
                                     str(a.get("entity", ""))))
    elif _sort_mode == "2":
        # entity-block sort (follow-up): metrics grouped per entity, block order = that entity's earliest
        # onset; keeps the opening while preserving the per-entity narrative (avoids the Tomcat loss). Content unchanged.
        _emin = {}
        for _a in m.get("anomalous", []):
            _o = _a.get("onset_ts")
            if _o is not None:
                _e = str(_a.get("entity", ""))
                _emin[_e] = min(_emin.get(_e, 9 * 10**18), int(_o))
        anos = sorted(m.get("anomalous", []),
                      key=lambda a: (_emin.get(str(a.get("entity", "")), 9 * 10**18),
                                     str(a.get("entity", "")),
                                     a.get("onset_ts") is None, int(a.get("onset_ts") or 0)))
    else:
        anos = sorted(m.get("anomalous", []), key=lambda a: (str(a.get("entity", "")), str(a.get("kpi", ""))))
    for a in anos:
        sh = a.get("shared_n", 1) or 1
        tag = f" [node-shared x{sh}]" if sh > 1 else ""
        sv, pts = _series_v4(a)
        onset = a.get("onset_ts")
        parts = [f"severity={_severity(a.get('max_z'))}"]
        if onset is not None:
            parts.append(f"onset@+{onset - t0}s" if t0 is not None else f"onset@{onset}")
        if pts is not None:
            parts.append(f"peak@+{pts - t0}s" if t0 is not None else f"peak@{pts}")
        _ann = ""
        if _mv2_idx is not None:
            _sig = _mv2_idx.get((str(a.get("entity")), str(a.get("kpi"))))
            if _sig is not None:
                _sh2 = _sig.get("case_shared") or 1
                _ann = (f" [baseline-check: fires in {_mv2_tier(_sig.get('bg_rate'), None if _mv2_bank else _mv2_nwin)}"
                        + (f"; same KPI fired on {_sh2} components now" if _sh2 > 1 else "") + "]")
            else:
                _ann = (f" [baseline-check: within this series' {_bl if not _mv2_bank else '10-day'} normal variation"
                        " — background-level]") if not _mv2_bank else (
                        " [baseline-check: within this series' 10-day normal variation"
                        " — background-level]")
        L.append(f"- {a['entity']} | {a['kpi']} ({', '.join(parts)}){tag}: [{sv}]{_ann}")

    if _mv2_idx is not None:
        _seen = {(str(a.get("entity")), str(a.get("kpi"))) for a in anos}
        _extra = []
        for _e in sorted(_mv2):
            _cnt = 0
            for _s in _mv2[_e]:
                if (_e, str(_s.get("kpi"))) in _seen:
                    continue
                _bg = _s.get("bg_rate")
                if _bg is None or _bg >= 0.02:
                    continue
                if _mv2_bank:
                    _abs = int(win.get("start") or 0) + int(_s.get("onset_s") or 0)
                    _on = f"onset@+{_abs - t0}s" if t0 is not None else f"onset@{_abs}"
                else:
                    # non-Bank: window time formats differ per dataset (ISO strings etc.), so use
                    # seconds relative to the window instead of epoch arithmetic
                    _on = f"onset@+{int(_s.get('onset_s') or 0)}s into the fault window"
                _sh2 = _s.get("case_shared") or 1
                _extra.append(f"- {_e} | {_s['kpi']} ({_on}, z={_s['z']} vs its {_bl} baseline;"
                              f" fires in {_mv2_tier(_bg, None if _mv2_bank else _mv2_nwin)})"
                              + (f" [same KPI on {_sh2} components now]" if _sh2 > 1 else ""))
                _cnt += 1
                if _cnt >= 3:
                    break
        if _extra:
            L.append(f"\n## Additional signals crossing z>=3 vs their own {_bl} baseline"
                     " (missed by the short-baseline detector above; same notation)")
            L.extend(_extra[:18])

    lg = case.get("logs", {}) or {}
    _lv2 = _logs_v2(case) if os.environ.get("RB_LOGS_V2") == "1" else None
    if _lv2 is not None:
        L.extend(_render_logs_v2(_lv2))
    elif lg.get("entries"):
        by_svc = {}
        for e in lg["entries"]:
            s = e.get("service", "") or e.get("pod", "")
            d = by_svc.setdefault(s, {"count": 0, "msg": str(e.get("message", "")).strip()})
            d["count"] += e.get("count", 1)
        L.append(f"\n## Error logs by service (total {lg.get('total_in_window')}, errors {lg.get('error_count')})")
        for s, d in sorted(by_svc.items(), key=lambda x: -x[1]["count"]):
            L.append(f"- {s}: {d['count']} errors — {d['msg'][:400]}")

    tr = case.get("traces", {}) or {}
    if tr.get("service_summary"):
        L.append(f"\n## Trace summary (total spans {tr.get('total_spans')}, error spans {tr.get('error_spans')})")
        if _lv2 is not None:
            _insts = ", ".join(sorted({str(x.get("service")) for x in tr["service_summary"]}))
            L.append(f"(Only these services are trace-instrumented: {_insts}. "
                     "Mysql, Redis and apache produce NO spans — absence of trace data there "
                     "is NOT evidence of health.)")
        for s in tr["service_summary"]:
            sr = s.get("slow_ratio_vs_peers")
            srtxt = f" [slow x{sr} vs peers]" if sr and sr >= 1.5 else ""
            lr = s.get("latency_ratio")
            lrtxt = (f" latency x{lr} vs own baseline" if _lv2 is not None
                     and isinstance(lr, (int, float)) and lr else "")
            L.append(f"- {s.get('service')}: spans={s.get('span_count')} err={s.get('error_count')} "
                     f"avg={s.get('avg_duration_ms')}ms p95={s.get('p95_duration_ms')}ms{lrtxt}{srtxt}")

    prop = m.get("propagation") or {}
    if prop and propagation != "none":
        L.extend(_render_propagation_v4(prop))
        if propagation == "full":
            L.append("Note: an anomaly can be a SYMPTOM propagated from a neighbor. For each candidate, check the "
                     "propagation direction (which side failed first / shows errors) before concluding it is the root "
                     "cause — do not decide by deviation magnitude alone.")

    if level == "metric":
        cands = sorted({a["kpi"] for a in m.get("anomalous", [])})
        L.append("\n## Candidate metrics (pick the TOP 3 most likely, verbatim):")
        L.append(", ".join(cands))
        return _sys_with_hint(SYS_V4_METRIC), "\n".join(L), cands, "metric"
    cands = list(m.get("all_entities", []))
    graph = get_graph_text(dataset, cands)
    if graph:
        L.append("\n" + graph)
    L.append("\n## Candidate components (pick the TOP 3 most likely, verbatim):")
    L.append(", ".join(cands))
    return _sys_with_hint(SYS_V4_COMPONENT), "\n".join(L), cands, "component"

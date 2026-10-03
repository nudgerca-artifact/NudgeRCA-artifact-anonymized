"""Static per-dataset Component Graph text: self-contained version (ported from an earlier common/topology.py).

The original reads the raw datasets/ (FoundRoot jsonl, Bank topology.json), but the raw data is not on the
cloud GPU instance, so this version reads static files pre-built into graphs/:
  - graphs/fr_edges_<letter>.json   : FoundRoot call_relations edge list
  - graphs/bank_component_graph.txt : OpenRCA/Bank component_graph_text
The mapping logic (_norm/_map_node) is the same as the original: names are normalized to each case's candidate names.
"""
import json, os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_GRAPHS = os.path.join(_HERE, "graphs")

FR_LETTER = {
    "Nezha/HipsterShop":  "J",
    "Nezha/TrainTicket":  "H",
    "Eadro/TrainTicket":  "G",
    "DejaVu/TrainTicket": "I",
    "OpenRCA/Telecom":    "A",
    "Eadro/SN":           "C",
    "GAIA/MicroSS":       "D",
    "AIOps2025":          "J",   # same topology as the HipsterShop app
}


def _norm(s):
    return re.sub(r"[\W_]+", "", str(s).lower(), flags=re.UNICODE)


def _fr_edges(letter):
    p = os.path.join(_GRAPHS, f"fr_edges_{letter}.json")
    if not os.path.exists(p):
        return set()
    return {tuple(e) for e in json.load(open(p))}


def _map_node(node, cand_norm):
    """FoundRoot node → our candidate (normalized substring match; pod hashes are absorbed automatically)."""
    n = _norm(node)
    if not n:
        return None
    for c, cn in cand_norm.items():
        if cn == n:
            return c
    best = None
    for c, cn in cand_norm.items():
        if cn.startswith(n) or n.startswith(cn):
            if best is None or len(cn) < len(cand_norm[best]):
                best = c
    return best


def get_graph_text(dataset, candidates):
    """'## Component Graph' text written with our candidate names. Empty string if none."""
    if dataset == "OpenRCA/Bank":
        p = os.path.join(_GRAPHS, "bank_component_graph.txt")
        return open(p).read() if os.path.exists(p) else ""
    if dataset == "DejaVu/Oracle":
        return ""
    letter = FR_LETTER.get(dataset)
    if not letter:
        return ""
    cand_norm = {c: _norm(c) for c in candidates}
    lines, seen = [], set()
    for a, b in sorted(_fr_edges(letter)):
        ma, mb = _map_node(a, cand_norm), _map_node(b, cand_norm)
        if ma and mb and ma != mb and (ma, mb) not in seen:
            seen.add((ma, mb))
            lines.append(f'- "{ma}" calls "{mb}"')
    if not lines:
        return ""
    head = ("## Component Graph\nThe call relationships between components in this system "
            "(\"X\" calls \"Y\" means X depends on Y):\n")
    return head + "\n".join(lines)

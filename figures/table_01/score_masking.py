#!/usr/bin/env python3
"""Table tab:masking: the untrained Qwen3-4B on 55 Bank incidents without injection, and with the reasoning structure of another
incident appended as a reference procedure, split by whether the structure's source incident has the same root-cause component.

outputs/no-injection/            one answer per incident (55)
outputs/injection-matrix/        every incident with every structure of data/structures.json (55 x 81 = 4,455)
outputs/same-cause-names-masked/ the 383 same-cause pairs (data/pairs_same_cause.json) with the component names in the structure
                                 replaced by "a component" (code/run_bruteforce.py --mask-structs)
All runs: temperature 0, top-p 0.95, top-k 20, repetition penalty 1.15, seed 42, thinking on, one answer per prompt.

Top-1: the first-ranked component matches the root cause (letters and digits kept, lowercased, the prediction contained in the
ground truth; code/common/matchers.py). Name: the first-ranked component equals the source component of the structure.
Family: the same after keeping only the leading letters (Tomcat02 -> tomcat).
Usage: python3 score_masking.py
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
def norm(x): return re.sub(r"[^一-龥a-zA-Z0-9]", "", str(x)).lower()
def match(p, g): p, g = norm(p), norm(g); return bool(p and g) and p in g
def fam(c):
    m = re.match(r"([A-Za-z]+)", str(c or "").strip()); return m.group(1).lower() if m else None
def load(sub): return [json.load(open(p)) for p in sorted(glob.glob(os.path.join(HERE, "outputs", sub, "*.json"))) if not p.endswith("_summary.json")]

def stats(rows, with_source):
    rows = [r for r in rows if r.get("pred")]
    top1 = sum(match(r["pred"][0], r["gt"]["component"]) for r in rows)
    assert top1 == sum(int(r["won"]) for r in rows)          # the stored outcome of the run
    out = {"n": len(rows), "top1": top1}
    if with_source:
        out["name"] = sum(norm(r["pred"][0]) == norm(r["member_component"]) for r in rows)
        out["family"] = sum(fam(r["pred"][0]) == fam(r["member_component"]) for r in rows)
    return out

base = load("no-injection"); matrix = load("injection-matrix"); masked = load("same-cause-names-masked")
same = [r for r in matrix if norm(r["member_component"]) == norm(r["gt"]["component"])]
diff = [r for r in matrix if norm(r["member_component"]) != norm(r["gt"]["component"])]
pairs = {(p["uuid"], p["member_uuid"]) for p in json.load(open(os.path.join(HERE, "data", "pairs_same_cause.json")))}
assert pairs == {(r["uuid"], r["member_uuid"]) for r in same} == {(r["uuid"], r["member_uuid"]) for r in masked}

pc = lambda k, s: f"{100 * s[k] / s['n']:.1f} % ({s[k]}/{s['n']})"
print("| Condition | Top-1 comp. | Name | Family |\n|---|---|---|---|")
for label, rows, src in [("No injection", base, False), ("Same cause, names kept", same, True),
                         ("Same cause, names masked", masked, False), ("Different cause, names kept", diff, True)]:
    s = stats(rows, src)
    print(f"| {label} | {pc('top1', s)} | " + (f"{pc('name', s)} | {pc('family', s)} |" if src else "- | - |"))
print(f"\nPairs: same cause {len(same)} (55 incidents), different cause {len(diff)} (one answer cut at the token limit, left out); "
      f"answers without a readable ranking are left out.")

"""Calibration prompts of the Int4 models: the training-pool prompts of bank (80), market (88) and telecom (30), in this order,
taken from nudgerca/preprocessing/rendered-inputs/train/. Usage: python make_calibration.py --out <calibration.jsonl>"""
import argparse, json, os
ART = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
T = os.path.join(ART, "nudgerca", "preprocessing", "rendered-inputs")
ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
pool = set(json.load(open(os.path.join(T, "splits", "bank.json")))["train_pool"])
rows = [r for r in map(json.loads, open(os.path.join(T, "train", "bank_all136.jsonl"))) if r["case_id"] in pool]
for ds in ("market", "telecom"): rows += list(map(json.loads, open(os.path.join(T, "train", f"{ds}.jsonl"))))
with open(a.out, "w") as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows), "calibration prompts ->", a.out)

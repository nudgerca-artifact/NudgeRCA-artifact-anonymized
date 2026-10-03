"""Error bars of Figure fig:size: for every bar, the standard deviation over the eight repetitions of the run (repetition k = response k of
every incident, see figures/common/per_sample.py) of Exact averaged over Telecom, Bank and Market. Reads the responses under data/ (Qwen3-4B
off-the-shelf and bf16 NudgeRCA: nudgerca/inference/outputs/), checks that the mean of the repetitions equals the value the figure plots, and
writes data/exact_sd.json. Usage: python3 code/collect_error_bars.py"""
import json, os, statistics, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(HERE, "..", "common"))
from per_sample import per_sample, sd   # noqa: E402
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
D = json.load(open(os.path.join(HERE, "data", "data_model_size.json"))); D.update(json.load(open(os.path.join(HERE, "data", "data_gemma_e4b.json"))))
DS = ["Telecom", "Bank", "Market"]; out = {}
def path(size, cond, d):
    if size.startswith("Gemma"): return os.path.join(HERE, "data", "gemma4-e4b", "outputs", cond, f"{d.lower()}.jsonl")
    key = f"{size}{'-Int4' if cond == 'int4' else ''}|{d}|{'ours' if cond == 'int4' else cond}"
    return os.path.join(ROOT, D[key]["src"])
for size in ("0.6B", "1.7B", "4B", "14B", "Gemma4-E4B"):
    end = "<channel|>" if size.startswith("Gemma") else "</think>"
    for cond in ("base", "ours", "int4"):
        reps = [per_sample(path(size, cond, d), end)[0] for d in DS]
        mean3 = [statistics.mean(x) for x in zip(*reps)]   # the three-dataset mean of each repetition
        key = lambda d: f"{size}{'-Int4' if cond == 'int4' else ''}|{d}|{'ours' if cond == 'int4' else cond}"
        for d, r in zip(DS, reps): assert abs(statistics.mean(r) - D[key(d)]["S"]) < 0.051, (size, cond, d, statistics.mean(r), D[key(d)]["S"])
        out[f"{size}|{cond}"] = {"mean": round(statistics.mean(mean3), 2), "sd": round(sd(mean3), 2)}
        print(f"{size:10s} {cond:5s} Exact {statistics.mean(mean3):5.1f} +- {sd(mean3):.1f}")
json.dump(out, open(os.path.join(HERE, "data", "exact_sd.json"), "w"), indent=1)

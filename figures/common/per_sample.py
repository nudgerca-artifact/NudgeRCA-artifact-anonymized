"""Per-sample accuracy for error bars. Every model run generates eight responses per incident; response k of every incident forms the k-th
repetition of the run. per_sample(path) scores each repetition separately (Exact and Partial over the incidents, %), so the mean over the
eight repetitions is the avg@8 of the paper and their standard deviation is the spread over repetitions that the error bars show."""
import json, os, statistics, sys
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "nudgerca", "inference"))
from score_openrca_corrected import parse_answer, task_score   # noqa: E402

def per_sample(path, end="</think>"):
    """Returns (exact, partial): lists with one value per repetition k (%). end: the token that closes the reasoning of the model family
    ("</think>" for Qwen3, "<channel|>" for Gemma 4); the answer is read after it, as in the paper's scoring."""
    rows = [json.loads(l) for l in open(path) if l.strip()]
    K = max(len(r["outputs"]) for r in rows); E = [[] for _ in range(K)]; P = [[] for _ in range(K)]
    for r in rows:
        for k, o in enumerate(r["outputs"]):
            s = task_score(parse_answer(o if end == "</think>" else o.replace(end, "</think>")), r["gt"])
            if s is None: continue
            E[k].append(1.0 if s >= 1.0 else 0.0); P[k].append(s)
    return [100 * statistics.mean(e) for e in E], [100 * statistics.mean(p) for p in P]

def sd(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0

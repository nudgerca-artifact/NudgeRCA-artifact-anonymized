# NudgeRCA data used by the figures and tables

- `preprocessing/rendered-inputs/eval/<dataset>.jsonl`: the input p (Algorithm 1) of every evaluation incident; `splits/<dataset>.json`: the
  training and evaluation incidents; `cases_eval.jsonl`: the ground truth of the 296 evaluation incidents.
- `inference/outputs/ours/<dataset>.jsonl`: eight responses per evaluation incident of NudgeRCA-4B (Qwen3-4B with the adapter of that dataset);
  `inference/outputs/base/<dataset>.jsonl`: the same for the off-the-shelf Qwen3-4B on the same input.
- `inference/score_openrca_corrected.py` (with `score_openrca_official.py`): the scorer of every number in the paper.

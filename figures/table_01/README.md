# Table 1: Accuracy with a few-shot diagnostic procedure

The reasoning of DeepSeek-R1 on another incident is appended to the input p of the off-the-shelf Qwen3-4B as a few-shot example, for 55 Bank
incidents: no injection, same root-cause component with names kept or masked, and a different root-cause component.

`table_01.py` (with `score_masking.py`) prints Top-1, Name and Family (`table_01.txt`). Responses: `outputs/` (one file per target incident
and injected example); pairs of incidents with the same cause: `data/pairs_same_cause.json`; the generation script: `code/run_bruteforce.py`.

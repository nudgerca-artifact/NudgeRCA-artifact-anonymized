# Shared helpers

- `tables.py`: paths of this artifact, the scorer (`nudgerca/inference/score_openrca_corrected.py`), the per-incident aggregation (each
  response scored separately, then averaged per incident and over incidents: avg@8) and the output helper used by the table scripts.
- `section3/`: the 648 trajectories of the off-the-shelf Qwen3-4B on 81 Bank incidents (eight per incident) that Section 3.2 and Fig. 3
  analyze (`data/bank_trajectories/trajectories/`), and `loaders.py`, which reads them. The Section 3.2 numbers leave out one incident
  whose final answer cannot be read (640 trajectories).

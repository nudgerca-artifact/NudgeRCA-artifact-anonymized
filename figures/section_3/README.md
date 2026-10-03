# Section 3.2: characteristics of root cause determination of the SLM

640 trajectories of the off-the-shelf Qwen3-4B on 80 Bank incidents (eight per incident) were judged twice independently with nine yes / no
questions (`behavior_judge/INSTRUCTIONS_judge.md`), and disagreements were resolved with an additional judgment
(`behavior_judge/INSTRUCTIONS_adjudicate.md`). `section3_numbers.py` prints:

- the shares of Behavior-1 (largest anomaly as the stated rationale, `q4_mag_rationale`), Behavior-2 (own analysis points to another
  component, `m2_self_contra`) and Behavior-3 (cites another component's signal, `q3_ungrounded`);
- the per-question agreement and Cohen's kappa of the two judgments;
- the first-listed candidate on the EOB input, and FoundRoot-14B on the input released by its authors.

Files: `behavior_judge/data/judge_inputs/` (the trajectories as given to the judges), `judge_outputs/A` and `B` (the two judgments),
`adjudication_inputs/` and `adjudication/` (the additional judgment of disagreements), `adjudicated.jsonl` (final answers),
`agreement.json`; `behavior_judge/*.py` build the inputs and aggregate the results; `input_vs_model_split/` holds the scripts of the last two
items.

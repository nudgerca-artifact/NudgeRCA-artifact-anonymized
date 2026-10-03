# Adjudication instructions (reviewer C)

Two independent reviewers judged yes/no questions about reasoning trajectories (definitions below, identical to INSTRUCTIONS_judge.md). You resolve only the questions where they disagreed. For each trajectory in the input file, read the case header and the full reasoning, then answer ONLY the questions listed under "QUESTIONS TO ADJUDICATE FOR THIS TRAJECTORY". Do not defer to either reviewer; decide from the text using the definitions. Their quotes are context, not evidence of correctness.

Definitions:
- q1_scan: examines anomalies of at least TWO candidate components evaluatively before deciding.
- q2_prop: explicitly reasons about propagation/dependency between components.
- q3_ungrounded: cites an observation about a component+signal pair that is NOT in the case header at all (numeric values are NOT checked; paraphrase of a listed signal is not ungrounded). "yes" only if you can name the absent component+signal pair.
- q4_mag_rationale: the stated basis for the FINAL top-1 is primarily anomaly size/severity (extreme, highest, largest, spike, peak, most severe) rather than a causal or temporal argument.
- q5_causal_chain: the final rationale names a concrete causal chain between two or more NAMED components.
- f_gt_considered: the ground-truth component is weighed as a POSSIBLE ROOT CAUSE at some point (not merely mentioned as victim/symptom/list item).
- m1_premature: commits to the largest/most-numerous-anomaly component BEFORE comparing the other candidates.
- m2_self_contra: the model's OWN propagation or timing analysis points to a different component than its final choice.
- m3_stop_after_commit: after committing to a top-1, no further candidate is evaluated.

Output: one JSON object per trajectory to the output path given to you, containing "job" and ONLY the disputed question keys with "yes"/"no" values, e.g. {"job": "...", "q3_ungrounded": "no", "m2_self_contra": "yes"}. One line per trajectory, nothing else in the file. Do not modify any other file. Finish with a one-line summary (trajectories adjudicated, items resolved).

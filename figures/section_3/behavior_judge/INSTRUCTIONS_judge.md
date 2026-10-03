# Trajectory judging instructions (Table behavior, Finding 2)

You are one of two independent reviewers. You read reasoning trajectories of a small language model (Qwen3-4B) doing root-cause analysis on a bank's microservice incident, and answer yes/no questions about HOW the model reasoned. Judge only from the text. Do not reward or penalize correctness; the `correct=` flag is given only so you can interpret the trajectory, and the ground truth is given only for the question about whether the model considered it.

Input file: one Markdown file with two cases. Each case has a header (ground truth, candidate list, the anomalous metrics the model saw grouped by entity and ordered by summed z-score, error logs, trace summary, propagation section) followed by 8 trajectories (final ranked answer with the model's own one-sentence rationale per rank, then the verbatim reasoning).

Answer these questions for EVERY trajectory (answer "yes" or "no" only):

- q1_scan: Does the reasoning examine the anomalies of at least TWO different candidate components before deciding (not merely list them, but say something evaluative about each)?
- q2_prop: Does the reasoning explicitly reason about propagation or dependency between components (upstream/downstream, caller/callee, cascade, "X affects Y", node shared by pods, etc.)?
- q3_ungrounded: Does the reasoning cite, as evidence, an observation about a component or a metric/log/trace signal that is NOT in the case header at all? Examples: a metric for a component that has no such signal listed; an error log for a service that has no error logs listed; a trace error for a service not in the trace summary. IMPORTANT: numeric values (percentages, byte counts, timestamps) are NOT to be checked, because the model saw the full value series which the header omits; a paraphrase of a listed signal is NOT ungrounded. Answer "yes" only if you can name a specific component+signal pair that is absent from the header.
- q4_mag_rationale: Is the stated basis for the FINAL top-1 choice primarily the size or severity of an anomaly (words like extreme, highest, largest, spike, peak, most severe, biggest deviation, strongest signal) rather than a causal or temporal argument?
- q5_causal_chain: Does the rationale for the final top-1 name a concrete causal chain between two or more NAMED components (e.g., "MG02 disk saturation caused Tomcat02 latency", "IG01 is upstream of Tomcat01 so ...")? A generic "may affect downstream services" without naming the other component is "no".
- f_gt_considered: Is the ground-truth component considered at some point as a POSSIBLE ROOT CAUSE (a candidate the model weighs), not merely mentioned as a victim, a symptom, or a name in a list?
- m1_premature: Does the model commit to the component with the largest or most numerous anomalies as the cause BEFORE it has compared the other candidates (i.e., the decision is stated first and the rest of the reasoning confirms it)?
- m2_self_contra: Does the model's OWN propagation or timing analysis point to a different component than the one it finally chooses (e.g., it says X is upstream of Y or X failed first, then picks Y)?
- m3_stop_after_commit: After committing to a top-1 candidate, does the model stop examining alternatives (no further candidate is evaluated)?

Also give `quote`: at most 20 words copied from the reasoning that best supports your q4 answer.

Output: write ONE JSON object per line (JSONL) to the output path given to you, exactly one line per trajectory, with these keys:
{"job": "<job id>", "q1_scan": "yes|no", "q2_prop": "yes|no", "q3_ungrounded": "yes|no", "q4_mag_rationale": "yes|no", "q5_causal_chain": "yes|no", "f_gt_considered": "yes|no", "m1_premature": "yes|no", "m2_self_contra": "yes|no", "m3_stop_after_commit": "yes|no", "quote": "..."}

Rules: read every trajectory fully before answering. Do not skip any job. Do not write anything else to the output file. Do not modify any other file. When done, reply with a one-line summary: number of jobs judged and the yes-counts per question.

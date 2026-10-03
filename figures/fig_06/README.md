# Fig. 6: Accuracy of each requested element as the input and the pair types are added cumulatively

Five steps, each scored with avg@8 on the evaluation incidents of the four datasets:

| Step | Responses |
|---|---|
| Off-the-shelf (off-the-shelf Qwen3-4B, input of prior data processing) | `baselines/prior-preprocessing/results/qwen3-4b/` |
| +EOB (off-the-shelf Qwen3-4B, EOB input) | `nudgerca/inference/outputs/base/` |
| +D_fork (adapter trained on D_fork) | `data/outputs/fork/` |
| +D_priv (adapter trained on D_fork and D_priv) | `data/outputs/fork-priv/` |
| +D_credit (NudgeRCA-4B, all pairs) | `nudgerca/inference/outputs/ours/` |

`build_fig06_data.py` scores every response and writes `data/ablation.json`; `fig_06.py` plots component, fault type and time accuracy over
all evaluation incidents (`fig_06.pdf`). The partial-credit pairs D_credit appear as `graded` in the data files.

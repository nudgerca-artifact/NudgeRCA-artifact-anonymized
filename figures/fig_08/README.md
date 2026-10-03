# Fig. 8: Change in accuracy by the length of the profiling period

For each incident, only the fault-free windows closest to it (before or after it) are kept, Historical Frequency Profiling is rerun on these
windows only, and NudgeRCA-4B is evaluated with the same adapter (eight responses per incident).

`collect_rq5.py` reads the scorer output of every run (`data/scores/<run>.txt`) and writes `data/rq5_final.csv` (system, share of the
fault-free windows, hours, Exact, Partial, their spread over the eight responses, and the confidence intervals of their changes); `fig_08.py` plots the change from the entire fault-free
period in percentage points (`fig_08.pdf`).

Shaded bands: +-1 standard deviation of each run over its eight responses per incident, the same measure as the error bars of the model-size
figure (response k of every incident is taken as the k-th repetition; `correct_sd`, `partial_sd` of `data/rq5_final.csv`). The csv also holds
the 95 % confidence interval of each change, from a bootstrap over incidents of the per-incident difference to the run on the entire fault-free
period (10,000 resamples, seed 0; `d_*_lo`, `d_*_hi`); `FIG8_STYLE=ci python3 fig_08.py <dir>` draws that interval as the band (hollow
markers where it includes 0) and `FIG8_STYLE=bars` as error bars. The responses of every run are in `data/outputs/<run>.jsonl`; the runs on
the entire fault-free period of Telecom and Bank are the paper's evaluation (`nudgerca/inference/outputs/ours/`).

`code/` holds the scripts that built the inputs of the runs (`interval_eob.py` for Bank and Telecom, `interval_eob_market_paper.py` for
Market, `sens_norm_slots.py` and `case_norms.py` for the log and trace baselines, `finalize.py` for the prompts). They need the raw
telemetry and the preprocessing pipeline and document how the inputs were built.

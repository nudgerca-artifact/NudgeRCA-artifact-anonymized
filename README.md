# NudgeRCA

Replication package of the paper *NudgeRCA: Guiding Small Language Model toward Root Cause Analysis with Context-Aware Reasoning
Refinement*. It contains the data and the scripts that regenerate the tables and the data figures of the paper.

## Install

Python 3.10 or newer. Run `pip install numpy pandas matplotlib`. No GPU, model weights or raw telemetry are needed.

## Contents

- `figures/`: one folder per figure or table of the paper (`fig_01` to `fig_08`, `table_01` to `table_04`), each with its script, its
  data (`data/`) and its output (`fig_NN.pdf` or `table_NN.txt`). `figures/section_3/` holds the trajectory judgments of Section 3.2, and
  `figures/common/` the shared helpers.
- `nudgerca/`: the evaluation inputs (the prompts of the evaluation incidents and the train / eval splits), the responses of NudgeRCA-4B and
  of the off-the-shelf Qwen3-4B, and the scorer (`inference/score_openrca_corrected.py`, the OpenRCA criteria of Section 5.1.2).
- `baselines/`: the outputs of the baseline systems on the same evaluation incidents, one folder per system.

## Reproducing the figures and tables

```bash
bash figures/reproduce_all.sh
```

Each script writes its output next to itself, so a single item can also be regenerated from its folder, for example
`cd figures/table_03 && python3 table_03.py`.

| Paper | Folder | Script | Output |
|---|---|---|---|
| Fig. 1 | `figures/fig_01/` | drawn | `fig_01a.pdf`, `fig_01b.pdf` |
| Fig. 2 | `figures/fig_02/` | `run.sh draw_normal_period.py` | `fig_02.pdf`, `tracks/` |
| Fig. 3 | `figures/fig_03/` | `select.py` | `data/candidates.json` |
| Section 3.2 | `figures/section_3/` | `section3_numbers.py` | `section3_numbers.txt` |
| Table 1 | `figures/table_01/` | `table_01.py` | `table_01.txt` |
| Fig. 4 | `figures/fig_04/` | drawn | `fig_04.pdf` |
| Fig. 5 | `figures/fig_05/` | drawn | `fig_05.pdf` |
| Table 2 | `figures/table_02/` | `table_02.py` | `table_02.txt` |
| Table 3 | `figures/table_03/` | `table_03.py` | `table_03.txt` |
| Fig. 6 | `figures/fig_06/` | `build_fig06_data.py`, `fig_06.py` | `fig_06.pdf` |
| Table 4 | `figures/table_04/` | `table_04.py` | `table_04.txt` |
| Fig. 7 | `figures/fig_07/` | `fig_07.py` | `fig_07.pdf` |
| Fig. 8 | `figures/fig_08/` | `collect_rq5.py`, `fig_08.py` | `fig_08.pdf` |

Figures 1, 4 and 5 are diagrams and are included as PDF files. Figure 2 is composed from the tracks that `draw_normal_period.py` plots,
and the excerpts of Figure 3 are taken from the two trajectory files in `figures/fig_03/data/trajectories/`.

## Data

The evaluation incidents come from the public OpenRCA (Telecom, Bank, Market) and AIOps 2025 benchmarks and from the four test benchmarks
released with FoundRoot (DejaVu-A, DejaVu-B, Eadro-SN, GAIA). The raw telemetry is available from the original releases.

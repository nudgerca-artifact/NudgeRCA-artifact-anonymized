#!/usr/bin/env bash
# Regenerate every table, every data figure and the in-text numbers of the paper from the files of this artifact
# (no GPU, no raw telemetry). Each script writes its output next to itself.
set -euo pipefail
cd "$(dirname "$0")"
export MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1
run() { echo; echo "===== $1 ${*:2}"; (cd "$(dirname "$1")" && python3 "$(basename "$1")" "${@:2}"); }

echo; echo "===== fig_02/draw_normal_period.py"      # Fig. 2 tracks and the Section 3.1 window counts
bash fig_02/run.sh draw_normal_period.py
run fig_03/select.py                            # Fig. 3 candidate trajectories
run section_3/section3_numbers.py                             # Section 3.2: Behavior-1 to 3, judge agreement and kappa
run table_01/table_01.py                        # Table 1
run table_02/table_02.py                                   # Table 2
run table_03/table_03.py                                   # Table 3
run fig_06/build_fig06_data.py                             # Fig. 6 data
run fig_06/fig_06.py                                       # Fig. 6
run table_04/table_04.py                                  # Table 4
(cd fig_07 && echo && echo "===== fig_07/code/collect_error_bars.py" && python3 code/collect_error_bars.py)   # Fig. 7 error bars
run fig_07/fig_07.py                                     # Fig. 7
run fig_08/collect_rq5.py                          # Fig. 8 data and error bars
run fig_08/fig_08.py                               # Fig. 8

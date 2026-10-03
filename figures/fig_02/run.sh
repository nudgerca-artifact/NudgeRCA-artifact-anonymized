#!/usr/bin/env bash
# Usage: bash run.sh draw_normal_sweep.py | draw_normal_period.py | prep_bands.py | baseline_sweep_bank.py
# Scripts read their inputs from the current directory, so this copies data/ and the scripts into work/ and runs there.
# prep_bands.py and baseline_sweep_bank.py need the raw Bank telemetry (see README); the two draw_* scripts run from data/ alone.
set -e; HERE=$(cd "$(dirname "$0")" && pwd); WORK=$HERE/work; mkdir -p $WORK
cp -n $HERE/data/* $WORK/ 2>/dev/null || true; cp $HERE/*.py $WORK/
cd $WORK && python3 "$1" "${@:2}"

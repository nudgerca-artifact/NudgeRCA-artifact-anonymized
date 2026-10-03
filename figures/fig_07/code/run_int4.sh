#!/usr/bin/env bash
# Rebuild the GPTQ Int4 model of one size and dataset from its trained adapter, then evaluate it like every model run of the paper
# (8 samples per incident, temperature 0.6) and score it. The adapter is merged in float32, quantized to W4A16 (group 128) with
# the training-pool prompts as calibration, and the float32 leftovers are cast to bfloat16.
# Usage: bash run_int4.sh <0.6b|1.7b|4b|8b|14b> <telecom|bank|market> [work dir]
# Needs one 48 GB GPU; the float32 merge of 8B and 14B needs about 64 GB of host memory.
set -euo pipefail
S=$1; D=$2; WORK=${3:-work}
HERE=$(cd "$(dirname "$0")" && pwd); FIG=$(cd "$HERE/.." && pwd); ART=$(cd "$HERE/../../.." && pwd)
declare -A BASE=([0.6b]=Qwen/Qwen3-0.6B [1.7b]=Qwen/Qwen3-1.7B [4b]=Qwen/Qwen3-4B [8b]=Qwen/Qwen3-8B [14b]=Qwen/Qwen3-14B)
declare -A MML=([telecom]=24576 [bank]=16384 [market]=24576)
if [ "$S" = 4b ]; then ADAPTER=$ART/nudgerca/adapters/ours/$D; else ADAPTER=$FIG/data/qwen3-$S/adapters/ours/$D; fi
mkdir -p "$WORK/outputs/qwen3-$S"; M=$WORK/merged_$S-$D; Q=$WORK/qwen3-$S-$D-int4; C=$WORK/calibration.jsonl
python3 "$HERE/make_calibration.py" --out "$C"
python3 "$HERE/merge_adapter.py" --base "${BASE[$S]}" --adapter "$ADAPTER" --out "$M" --dtype float32
python3 "$HERE/quantize_gptq.py" --model "$M" --calib "$C" --n 256 --seq 4096 --seed 42 --out "$Q"
python3 "$HERE/fix_quant_config.py" "$Q"; python3 "$HERE/cast_saved.py" "$Q"; rm -rf "$M"
OUT=$WORK/outputs/qwen3-$S/$D.jsonl
python3 "$ART/nudgerca/inference/gen_openrca_tasks_fast.py" --model "$Q" --in "$ART/nudgerca/preprocessing/rendered-inputs/eval/$D.jsonl" \
  --out "$OUT" --n 8 --max-model-len "${MML[$D]}"
python3 "$ART/nudgerca/inference/score_openrca_corrected.py" "$OUT" "qwen3-$S-int4-$D"

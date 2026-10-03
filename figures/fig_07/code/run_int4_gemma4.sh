#!/usr/bin/env bash
# Rebuild the GPTQ Int4 model of the Gemma 4 E4B NudgeRCA adapter of one dataset and evaluate it like every model run of the paper
# (8 samples per incident, temperature 0.6, bf16 activations), then probe its latency. The adapter is merged in float32 on the GPU
# (merge_adapter_gemma4.py also copies the processor and chat-template files vLLM needs), quantized to W4A16 (group 128) over every linear
# layer of the language model with the training-pool prompts as calibration, and the float32 leftovers are cast to bfloat16.
# Usage: bash run_int4_gemma4.sh <telecom|bank|market> <adapter dir> [work dir]
# Needs one 80 GB GPU for the quantization (float32 weights plus the GPTQ Hessians of every layer); evaluation and the latency probe run on one L40S.
# Environment: vllm 0.30, transformers 5.17, llmcompressor 0.14, compressed-tensors 0.19 (Gemma 4 is not supported by the vllm 0.11 pin of the Qwen3 runs).
set -euo pipefail
D=$1; ADAPTER=$2; WORK=${3:-work}; export FAMILY=gemma4
HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../../.." && pwd); BASE=google/gemma-4-E4B-it
declare -A MML=([telecom]=24576 [bank]=24576 [market]=24576)
mkdir -p "$WORK/outputs/gemma4-e4b" "$WORK/latency"; M=$WORK/merged_gemma4-e4b-$D; Q=$WORK/gemma4-e4b-$D-int4; C=$WORK/calibration.jsonl
python3 "$HERE/make_calibration.py" --out "$C"
python3 "$HERE/merge_adapter_gemma4.py" --base "$BASE" --adapter "$ADAPTER" --out "$M" --dtype float32 --device cuda
python3 "$HERE/quantize_gptq_gemma4.py" --model "$M" --calib "$C" --n 256 --seq 4096 --seed 42 --group-size 128 --damp 0.01 --targets google --gpu-mem 40GiB --out "$Q"
python3 "$HERE/fix_quant_config.py" "$Q"; python3 "$HERE/cast_saved.py" "$Q"; rm -rf "$M"
EVAL=$ART/nudgerca/preprocessing/rendered-inputs/eval/$D.jsonl; OUT=$WORK/outputs/gemma4-e4b/$D.jsonl
python3 "$ART/nudgerca/inference/gen_openrca_tasks_fast.py" --model "$Q" --in "$EVAL" --out "$OUT" --n 8 --max-model-len "${MML[$D]}" --dtype bfloat16
python3 "$ART/nudgerca/inference/score_openrca_corrected.py" "$OUT" "gemma4-e4b-int4-$D"
python3 "$HERE/latency_probe_gemma4.py" --model "$Q" --dtype bfloat16 --in "$EVAL" --k 10 --out "$WORK/latency/Gemma4-E4B_trained-int4_$D.json"

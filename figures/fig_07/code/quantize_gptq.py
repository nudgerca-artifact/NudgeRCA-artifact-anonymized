"""GPTQ W4A16 (group 128) with llm-compressor, calibrated on our training-pool prompts (all 198 in the default run).
Usage: python quantize_gptq.py --model <merged dir> --calib <prompt jsonl...> --n 256 --seq 4096 --out <dir>"""
import argparse, json, random
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
try:
    from llmcompressor.modifiers.gptq import GPTQModifier          # current module path
except ImportError:
    from llmcompressor.modifiers.quantization import GPTQModifier  # older releases
ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--calib", nargs="+", required=True)
ap.add_argument("--n", type=int, default=256); ap.add_argument("--seq", type=int, default=4096); ap.add_argument("--out", required=True)
ap.add_argument("--scheme", default="W4A16"); ap.add_argument("--seed", type=int, default=42); a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype="auto")   # loaded on CPU; oneshot moves one layer at a time to the GPU
rows = []
for p in a.calib:
    for l in open(p):
        r = json.loads(l)
        rows.append(tok.apply_chat_template([{"role": "system", "content": r["system"]}, {"role": "user", "content": r["prompt"]}],
                                            tokenize=False, add_generation_prompt=True, enable_thinking=True))
random.Random(a.seed).shuffle(rows); rows = rows[:a.n]
ds = Dataset.from_dict({"text": rows})
ds = ds.map(lambda b: tok(b["text"], padding=False, max_length=a.seq, truncation=True, add_special_tokens=False), remove_columns=["text"])
recipe = GPTQModifier(targets="Linear", scheme=a.scheme, ignore=["lm_head"])
oneshot(model=model, dataset=ds, recipe=recipe, max_seq_length=a.seq, num_calibration_samples=len(rows))
model.save_pretrained(a.out, save_compressed=True); tok.save_pretrained(a.out)
print(f"quantized {a.model} → {a.out} | scheme {a.scheme} | calib {len(rows)}×≤{a.seq}")

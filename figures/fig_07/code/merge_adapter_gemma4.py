"""Merge a LoRA adapter into its base model in float32 and save the merged weights.
For Gemma 4 evaluation: vLLM hangs when a Gemma 4 LoRA adapter is attached at runtime, so the adapter is merged in float32
(a bfloat16 merge rounds away the small LoRA update) and the merged model is served with dtype float32. --device cuda merges on the GPU
(instances with 30 GB RAM cannot hold an 8B float32 model). Non-weight files of the base snapshot (processor, chat template) are copied.
Usage: python merge_adapter.py --base <dir> --adapter <adapter dir> --out <dir> [--dtype float32|bfloat16] [--device cpu|cuda]"""
import argparse, glob, os, shutil, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--adapter", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--dtype", default="float32", choices=["float32", "bfloat16"]); ap.add_argument("--device", default="cpu"); a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.base)
model = AutoModelForCausalLM.from_pretrained(a.base, torch_dtype=getattr(torch, a.dtype), device_map=a.device, low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, a.adapter).merge_and_unload()
model.save_pretrained(a.out, safe_serialization=True); tok.save_pretrained(a.out)
for f in glob.glob(os.path.join(a.base, "*")):
    n = os.path.basename(f)
    if not n.endswith((".safetensors", ".bin")) and n != "model.safetensors.index.json" and not os.path.exists(os.path.join(a.out, n)) and os.path.isfile(f):
        shutil.copy(f, os.path.join(a.out, n))
print("merged ->", a.out, "|", a.dtype, "|", a.device)

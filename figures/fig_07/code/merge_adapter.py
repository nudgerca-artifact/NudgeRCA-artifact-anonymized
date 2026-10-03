"""Merge a LoRA adapter into its base model and save the merged weights (input of quantize_gptq.py).
The merge is computed in float32 by default.
Usage: python merge_adapter.py --base Qwen/Qwen3-4B --adapter <adapter dir> --out <dir> [--dtype float32|bfloat16]"""
import argparse, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--adapter", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--dtype", default="float32", choices=["float32", "bfloat16"]); a = ap.parse_args()
tok = AutoTokenizer.from_pretrained(a.base)
model = AutoModelForCausalLM.from_pretrained(a.base, torch_dtype=getattr(torch, a.dtype), device_map="cpu", low_cpu_mem_usage=True)
model = PeftModel.from_pretrained(model, a.adapter).merge_and_unload()
model.save_pretrained(a.out, safe_serialization=True); tok.save_pretrained(a.out)
print("merged ->", a.out, "|", a.dtype)

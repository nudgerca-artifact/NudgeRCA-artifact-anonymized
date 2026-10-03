"""GPTQ W4A16 (group size 128) of the float32-merged Gemma 4 E4B NudgeRCA with llm-compressor, calibrated on the 198 training-pool
prompts (seed 42, n 256, seq 4096; prompt built as in evaluation). Calibration runs through the whole model (Gemma 4 shares the KV states
of the last non-shared layer with its last 18 layers, so layer-by-layer calibration fails) with the model split over the visible GPUs; the
modules that are neither quantized nor adapted (per-layer embedding table, vision/audio towers) stay in bfloat16, their checkpoint precision.
--targets google : every nn.Linear of the language model except the towers and lm_head (the 343 modules that google/gemma-4-E4B-it-qat-w4a16-ct quantizes)
--targets proj   : only q/k/v/o/gate/up/down (258 modules); the partially quantized checkpoint this produces does not load correctly in vLLM
Usage: FAMILY=gemma4 python quantize_gptq_gemma4.py --model <merged dir> --calib <jsonl> --out <dir> [--group-size 128] [--damp 0.01] [--targets google] [--gpu-mem 40GiB]"""
import argparse, glob, json, os, random, shutil, sys
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from llmcompressor import oneshot
try:
    from llmcompressor.modifiers.gptq import GPTQModifier
except ImportError:
    from llmcompressor.modifiers.quantization import GPTQModifier
from compressed_tensors.quantization import QuantizationArgs, QuantizationScheme
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import family
ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--calib", nargs="+", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=256); ap.add_argument("--seq", type=int, default=4096); ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--group-size", type=int, default=128); ap.add_argument("--damp", type=float, default=0.01); ap.add_argument("--targets", default="google", choices=["google", "proj"])
ap.add_argument("--gpu-mem", default="17GiB"); a = ap.parse_args()
import torch
from accelerate import dispatch_model, infer_auto_device_map
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype="auto")
for n, m in model.named_modules():
    if n.endswith("embed_tokens_per_layer") or any(k in n.split(".")[1:3] for k in ("vision_tower", "audio_tower", "embed_vision", "embed_audio")):
        m.to(torch.bfloat16)
        if n.endswith("embed_tokens_per_layer"): m.register_forward_hook(lambda mod, inp, out: out.float())
ngpu = torch.cuda.device_count()
dm = infer_auto_device_map(model, max_memory={**{i: a.gpu_mem for i in range(ngpu)}, "cpu": "600GiB"}, no_split_module_classes=model._no_split_modules)
print("device map:", {d: sum(1 for v in dm.values() if v == d) for d in set(dm.values())}, flush=True)
model = dispatch_model(model, device_map=dm)
rows = [family.gen_prompt(tok, json.loads(l)["system"], json.loads(l)["prompt"]) for p in a.calib for l in open(p)]
random.Random(a.seed).shuffle(rows); rows = rows[:a.n]
ds = Dataset.from_dict({"text": rows}).map(lambda b: tok(b["text"], padding=False, max_length=a.seq, truncation=True, add_special_tokens=False), remove_columns=["text"])
IGN = ["re:.*vision_tower.*", "re:.*audio_tower.*", "re:.*embed_vision.*", "re:.*embed_audio.*", "lm_head"]
if a.targets == "google": T = ["Linear"]
else: T = [r"re:.*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"]
scheme = QuantizationScheme(targets=T, weights=QuantizationArgs(num_bits=4, type="int", symmetric=True, strategy="group", group_size=a.group_size))
recipe = GPTQModifier(config_groups={"group_0": scheme}, ignore=IGN, dampening_frac=a.damp)
oneshot(model=model, processor=tok, dataset=ds, recipe=recipe, max_seq_length=a.seq, num_calibration_samples=len(rows), pipeline="basic")
model.save_pretrained(a.out, save_compressed=True); tok.save_pretrained(a.out)
for f in glob.glob(os.path.join(a.model, "*")):
    n = os.path.basename(f)
    if os.path.isfile(f) and not n.endswith((".safetensors", ".bin")) and n != "model.safetensors.index.json" and not os.path.exists(os.path.join(a.out, n)): shutil.copy(f, os.path.join(a.out, n))
q = json.load(open(os.path.join(a.out, "config.json"))).get("quantization_config", {})
print(f"quantized {a.model} -> {a.out} | targets {a.targets} group {a.group_size} damp {a.damp} | ignore list {len(q.get('ignore') or [])} | calib {len(rows)}x<={a.seq}", flush=True)

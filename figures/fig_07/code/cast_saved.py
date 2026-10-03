"""Cast the float32 tensors left in a saved quantized model (embeddings, norms, scales of a float32-merged input) to bfloat16
and set the config dtype. Integer tensors (packed weights) are left as they are. Usage: python cast_saved.py <quantized model dir>"""
import glob, json, os, sys, torch
from safetensors.torch import load_file, save_file
d = sys.argv[1]; n = 0
for f in sorted(glob.glob(os.path.join(d, "*.safetensors"))):
    t = load_file(f)
    for k, v in t.items():
        if v.dtype == torch.float32: t[k] = v.to(torch.bfloat16); n += 1
    save_file(t, f, metadata={"format": "pt"})
p = os.path.join(d, "config.json"); cfg = json.load(open(p))
for k in ("dtype", "torch_dtype"):
    if k in cfg: cfg[k] = "bfloat16"
json.dump(cfg, open(p, "w"), indent=2); print(f"cast {n} float32 tensors to bfloat16 in {d}")

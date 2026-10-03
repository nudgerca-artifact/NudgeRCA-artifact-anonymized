"""Remove the None-valued fields (scale_dtype, zp_dtype) that llm-compressor writes and vLLM 0.11.0 rejects.
Usage: python fix_quant_config.py <quantized model dir>"""
import json, sys, os
p = os.path.join(sys.argv[1], "config.json"); cfg = json.load(open(p))
removed = []
def strip(o, path=""):
    if isinstance(o, dict):
        for k in list(o.keys()):
            if o[k] is None: removed.append(path + k); del o[k]
            else: strip(o[k], path + k + ".")
    elif isinstance(o, list):
        for i, v in enumerate(o): strip(v, f"{path}[{i}].")
qc = cfg.get("quantization_config")
if qc is None: sys.exit("no quantization_config in " + p)
strip(qc, "quantization_config.")
json.dump(cfg, open(p, "w"), indent=2); print("removed None fields:", removed)

#!/usr/bin/env python3
"""The paper's model-size figure (Figure fig:size): for Qwen3 0.6B, 1.7B, 4B and 14B (and Gemma 4 E4B after the divider: off-the-shelf, NudgeRCA bf16 and NudgeRCA Int4), Exact averaged over the three OpenRCA datasets (telecom,
bank, market) as bars for the off-the-shelf model on the EOB input, NudgeRCA (bf16) and NudgeRCA Int4 (each trained size merged in float32 and
quantized to GPTQ W4A16), and seconds per incident on one L40S as lines (right axis) for NudgeRCA bf16 and Int4.
Reads data/data_model_size.json, data/data_gemma_e4b.json, data/latency/summary_l40s.json (code/collect_latency.py), data/latency/gemma_l40s.json and
data/exact_sd.json (error bars: standard deviation over the eight repetitions, code/collect_error_bars.py). Output: fig_07.pdf.
Usage: python3 fig_07.py [<data dir>] [<output dir>]"""
import json, os, sys
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data")
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else HERE
D = json.load(open(os.path.join(DATA, "data_model_size.json")))
D.update(json.load(open(os.path.join(DATA, "data_gemma_e4b.json"))))   # Gemma 4 E4B: same evaluation inputs, 8 samples, avg over the three datasets
LAT = json.load(open(os.path.join(DATA, "latency", "summary_l40s.json")))["models"]
_LG = json.load(open(os.path.join(DATA, "latency", "gemma_l40s.json")))
LATG = _LG["Gemma4-E4B-trained"]["mean_three_datasets"]["s_per_incident"]   # Gemma 4 E4B NudgeRCA, bf16, one L40S
LATG4 = _LG["Gemma4-E4B-trained-int4"]["mean_three_datasets"]["s_per_incident"]   # Gemma 4 E4B NudgeRCA, GPTQ Int4, one L40S
SDV = json.load(open(os.path.join(DATA, "exact_sd.json")))   # "<size>|<base|ours|int4>": {"mean", "sd"} of the three-dataset Exact
ERR = dict(elinewidth=0.6, capsize=1.4, capthick=0.6, ecolor="#3a3a3a")
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 10,
                     "xtick.labelsize": 10, "ytick.labelsize": 9.5, "legend.fontsize": 10, "axes.linewidth": 0.9, "hatch.linewidth": 0.5})
SIZES = ["0.6B", "1.7B", "4B", "14B", "Gemma4-E4B"]; TICK = {"Gemma4-E4B": "E4B"}; DS = ["Telecom", "Bank", "Market"]; FS = 9; WH = 0.19
LABEL = {"base": "Off-the-shelf\nbf16", "ours": "NudgeRCA\nbf16", "int4": "NudgeRCA\nInt4"}   # method on the first line, precision on the second
BAR = {"base": dict(color="#E3E3E3", edgecolor="#7F7F7F", hatch="....", linewidth=0.6),   # the off-the-shelf model (no latency line)
       "ours": dict(color="#9DB7D6", edgecolor="#3B6EA5", linewidth=0.6),
       "int4": dict(color="#F3C08F", edgecolor="#C46F10", hatch="////", linewidth=0.6)}
LINE = {"ours": dict(color="#3B6EA5", marker="o", ls="-", lw=1.5, ms=4.4, mec="white", mew=0.7),
        "int4": dict(color="#C46F10", marker="s", ls=(0, (4, 2)), lw=1.5, ms=4.0, mec="white", mew=0.7)}

def v(k, key):
    x = D.get(k); return np.nan if not x or x.get(key) is None else x[key]
def acc(size, name):   # mean Exact over the three datasets; "base" = the same model without the adapter, on the EOB input
    if name == "base": return float(np.nanmean([v(f"{size}|{d}|base", "S") for d in DS]))
    return float(np.nanmean([v(f"{size}{'-Int4' if name == 'int4' else ''}|{d}|ours", "S") for d in DS]))
def lat(size, name):   # mean seconds per incident over the three datasets; the 4B entries are keyed "trained" / "trained-int4"
    cond = "trained" if name == "ours" else "trained-int4"
    m = LAT.get(cond if size == "4B" else f"{size}-{cond}")
    return np.nan if not m else m["mean_three_datasets"]["s_per_incident"]

fig, ax = plt.subplots(figsize=(3.45, 1.62)); ax2 = ax.twinx(); bars = ("base", "ours", "int4")
XPOS = {"0.6B": 0.0, "1.7B": 1.0, "4B": 2.0, "14B": 3.0, "Gemma4-E4B": 4.1}   # Gemma (two bars) at the right end, after a divider
for s in SIZES:
    names = bars
    for j, name in enumerate(names):
        ax.bar(XPOS[s] + (j - (len(names) - 1) / 2) * WH, acc(s, name), width=WH * 0.93, zorder=3, yerr=SDV[f"{s}|{name}"]["sd"], error_kw=dict(ERR, zorder=4), **BAR[name])
GAP = (XPOS["Gemma4-E4B"] - WH * 1.25, XPOS["Gemma4-E4B"] + WH * 1.25)   # the Qwen latency lines are interrupted over the Gemma bars
for name in ("ours", "int4"):
    qs = [s for s in SIZES if not s.startswith("Gemma") and not np.isnan(lat(s, name))]
    xs, ys = [XPOS[s] for s in qs], [lat(s, name) for s in qs]
    segs, cur = [], [(xs[0], ys[0])]
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if x0 < GAP[0] and x1 > GAP[1]:
            yi = lambda x: y0 + (y1 - y0) * (x - x0) / (x1 - x0)
            cur.append((GAP[0], yi(GAP[0]))); segs.append(cur); cur = [(GAP[1], yi(GAP[1]))]
        cur.append((x1, y1))
    segs.append(cur)
    style = {k: x for k, x in LINE[name].items() if k not in ("marker", "ms", "mec", "mew")}
    for seg in segs: ax2.plot([p[0] for p in seg], [p[1] for p in seg], zorder=4, **style)
    ax2.plot(xs, ys, ls="none", zorder=5, **{k: x for k, x in LINE[name].items() if k in ("color", "marker", "ms", "mec", "mew")})
for name, y in (("ours", LATG), ("int4", LATG4)):   # Gemma: single points over its bars, not on the Qwen3 lines
    ax2.plot([XPOS["Gemma4-E4B"] + (0 if name == "ours" else WH)], [y], ls="none", zorder=5, **{k: x for k, x in LINE[name].items() if k in ("color", "marker", "ms", "mec", "mew")})
ax.set_xticks([XPOS[x] for x in SIZES]); ax.set_xticklabels([TICK.get(x, x) for x in SIZES], fontsize=FS); ax.tick_params(axis="x", length=0, pad=2)
ax.set_xlim(-0.5, XPOS["Gemma4-E4B"] + 0.6); DIV = (XPOS["14B"] + 1.5 * WH + XPOS["Gemma4-E4B"] - WH) / 2; ax.axvline(DIV, color="#8a8a8a", ls=(0, (3, 2)), lw=0.9, zorder=1)   # full-height divider between the two families
ax.set_ylim(0, 40); ax.set_yticks(range(0, 41, 10)); ax2.set_ylim(0, 80); ax2.set_yticks(range(0, 81, 20))
ax.text(-0.38, 38.6, "Qwen3", ha="left", va="top", fontsize=7.5, color="#555555")   # family names inside the plot, one per side of the divider
ax.text((DIV + XPOS["Gemma4-E4B"] + 0.6) / 2, 38.6, "Gemma 4", ha="center", va="top", fontsize=7.5, color="#555555")
ax.set_ylabel("Exact (%)", labelpad=1.5, fontsize=FS); ax2.set_ylabel("Seconds per incident", labelpad=2, fontsize=FS)
ax.grid(axis="y", ls="-", color="#e6e6e6", lw=0.6, zorder=0); ax.set_axisbelow(True)
for a in (ax, ax2): a.tick_params(axis="y", length=2, pad=1.2, labelsize=8.5)
swatch = lambda n: Patch(**{k: x for k, x in BAR[n].items() if k != "color"}, facecolor=BAR[n]["color"])
handles = [swatch(n) if n == "base" else (swatch(n), Line2D([0], [0], **LINE[n])) for n in bars]   # one entry per model: its bar and its line
leg = ax.legend(handles, [LABEL[n] for n in bars], handler_map={tuple: HandlerTuple(ndivide=None, pad=0.5)}, loc="lower center", bbox_to_anchor=(0.5, 1.0),
          ncol=3, frameon=False, handlelength=1.8, handleheight=0.7, fontsize=8.5, borderaxespad=0.1, columnspacing=0.9, handletextpad=0.3)   # two-line labels keep the legend within the width of the plot
fig.tight_layout(pad=0.15); out = os.path.join(OUTDIR, "fig_07.pdf")
fig.canvas.draw(); _l, _a = leg.get_window_extent(), ax.get_window_extent(); print(f"legend width {_l.width / fig.dpi:.2f} in, plot width {_a.width / fig.dpi:.2f} in")
fig.savefig(out, bbox_inches="tight", pad_inches=0.015); print("saved", out)
fig.savefig(out[:-4] + ".png", bbox_inches="tight", pad_inches=0.015, dpi=300)   # preview for viewers that do not render the PDF

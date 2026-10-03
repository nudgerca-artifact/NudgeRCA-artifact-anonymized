#!/usr/bin/env python3
"""Figure 6, with the value of every point: component, fault type and time accuracy over all incidents for the
five steps of the ladder. Same data, series, labels and styles as the earlier per-dataset version (data/ablation.json). Output: fig_06.pdf."""
import json, os, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data")
OUTDIR = sys.argv[2] if len(sys.argv) > 2 else HERE
D = json.load(open(os.path.join(DATA, "ablation.json")))
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 10,
                     "xtick.labelsize": 8.5, "ytick.labelsize": 9.5, "legend.fontsize": 8.5, "axes.linewidth": 0.9})
STEPS = ["1 prior-prep, no adapter", "2 ours-prep, no adapter", "3 + fork", "4 + privilege", "5 + graded = ours"]
SHORT = ["Off-the-shelf", "+EOB", r"+$\mathcal{D}_{\mathrm{fork}}$", r"+$\mathcal{D}_{\mathrm{priv}}$", r"+$\mathcal{D}_{\mathrm{credit}}$"]
SER_B = [("comp", "Component", "#2C7C6E", "s", "-", 1.8), ("reason", "Fault type", "#8B5FA8", "D", (0, (5, 2.2)), 1.8), ("time", "Time", "#E08214", "v", (0, (1.4, 1.6)), 1.8)]
# label offsets (dx in steps, dy in points of accuracy) per series; the first step is crowded (component 20.8 vs time 19.6)
OFF = {"time": (0, 3.6, "bottom", "center"), "comp": (0.12, -1.4, "top", "left"), "reason": (0, -3.6, "top", "center")}   # component: right of its marker, between the lines
OFF0 = {"comp": (-0.12, 2.6, "center", "right"), "time": (-0.12, -2.2, "center", "right"), "reason": (0, -3.6, "top", "center")}   # first step: both values on the left of the overlapping markers
OFF4 = {}
K = 1.8 / 1.35   # the figure is shorter than before (1.35 in, was 1.8 in): scale the label offsets so their distance from the markers stays the same
OFF = {k: (dx, dy * K, va, ha) for k, (dx, dy, va, ha) in OFF.items()}; OFF0 = {k: (dx, dy * K, va, ha) for k, (dx, dy, va, ha) in OFF0.items()}
OFF["comp"] = (0.10, -0.4, "top", "left")   # component values sit just under their line, clear of the fault-type line below
fig, ax = plt.subplots(figsize=(2.3, 1.35))
for mk, lbl, c, mrk, ls, lw in SER_B:
    y = [D[s]["all"][mk] for s in STEPS]
    ax.plot(range(5), y, marker=mrk, color=c, lw=lw, ls=ls, ms=4.8, mec="white", mew=.7, label=lbl, zorder=3)
    for i, v in enumerate(y):
        dx, dy, va, ha = (OFF0 if i == 0 else OFF4 if (i == 4 and mk in OFF4) else OFF)[mk]
        ax.text(i + dx, v + dy, f"{v:.1f}", ha=ha, va=va, fontsize=6.3, color="#333333", zorder=4)
# (title removed: the caption says the panel is over all incidents)
ax.set_xticks(range(5)); ax.set_xlim(-0.7, 4.75); ax.set_ylim(0, 75); ax.set_yticks(range(0, 76, 25))
ax.axvspan(-0.7, 0.5, color="#000000", alpha=.06); ax.tick_params(axis="x", length=0, pad=1.5); ax.tick_params(axis="y", length=2.5, pad=1.5)
ax.set_xticklabels(SHORT, rotation=30, ha="right", rotation_mode="anchor")
from matplotlib.transforms import ScaledTranslation
for t in ax.get_xticklabels(): t.set_transform(t.get_transform() + ScaledTranslation(6 / 72, 0, fig.dpi_scale_trans))   # shift each rotated label right so it sits under its tick
ax.grid(axis="y", ls="-", color="#e6e6e6", lw=0.6); ax.set_axisbelow(True)
for xv in range(5): ax.axvline(xv, color="#b5b5b5", ls=(0, (1.2, 1.8)), lw=0.7, zorder=0.8)
ax.set_ylabel("Accuracy (%)", labelpad=2)
h, l = ax.get_legend_handles_labels()
ORDER = ["Fault type", "Component", "Time"]   # the legend reads in the vertical order of the lines (lowest to highest)
h, l = [h[l.index(k)] for k in ORDER], ORDER
fig.legend(h, l, loc="upper center", bbox_to_anchor=(0.55, 1.03), ncol=3, frameon=False, handlelength=1.6, columnspacing=0.5, handletextpad=0.25, borderaxespad=0.1)
fig.subplots_adjust(left=0.17, right=0.98, bottom=0.22, top=0.86)
out = os.path.join(OUTDIR, "fig_06.pdf"); fig.savefig(out, bbox_inches="tight", pad_inches=0.015); print("saved", out)
fig.savefig(out[:-4] + ".png", bbox_inches="tight", pad_inches=0.015, dpi=300)   # preview for viewers that do not render the PDF

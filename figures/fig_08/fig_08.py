"""The paper's RQ5 figure (Figure fig:sensitivity), drawn at half the text width: one panel per system, Partial and Exact as the change (percentage points) from
profiling on the entire fault-free period, x = the fault-free period used for profiling (absolute time, log scale). Measured points only.
Shaded: +-1 standard deviation of each run over its eight responses per incident (the measure of the model-size figure); FIG8_STYLE=ci / bars draw the 95 % confidence interval of the change instead. Data: data/rq5_final.csv (collect_rq5.py). Output: fig_08.pdf. Usage: python3 fig_08.py"""
import os, csv, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); P = {}
for r in csv.DictReader(open(os.path.join(HERE, "data", "rq5_final.csv"))):
    P.setdefault(r["system"], {})[float(r["hours"])] = (float(r["correct"]), float(r["partial"]), (float(r["d_correct_lo"]), float(r["d_correct_hi"])),
                                                       (float(r["d_partial_lo"]), float(r["d_partial_hi"])), float(r["correct_sd"]), float(r["partial_sd"]))
STYLE = os.environ.get("FIG8_STYLE", "sd")   # "sd" (default): band = +-1 standard deviation of the run over its eight responses per incident, the
# same measure as the error bars of the model-size figure; "ci": band = 95 % confidence interval of the change (paired bootstrap over incidents),
# hollow markers where it includes 0; "bars": the interval as error bars
plt.rcParams.update({"font.family": "serif", "font.serif": ["Nimbus Roman", "STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
                     "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 8, "axes.linewidth": 0.7})
SER = [(1, "Partial", "#3B6EA5", "o", "-", 1.3), (0, "Exact", "#D1495B", "^", (0, (4, 1.8)), 1.3)]   # the ablation figure's styles
TK = {"Telecom": ([1, 24], ["1 h", "1 d"]), "Bank": ([2, 24, 211.5], ["2 h", "1 d", "8.8 d"]), "Market": ([2, 18], ["2 h", "18 h"])}
fig, axes = plt.subplots(1, 3, figsize=(2.9, 1.45), sharey=True)
for ax, s in zip(axes, ("Telecom", "Bank", "Market")):
    xs = sorted(P[s]); full = P[s][max(xs)]
    for i, lbl, c, mrk, ls, lw in SER:
        y = [P[s][x][i] - full[i] for x in xs]
        if STYLE == "sd":
            e = [P[s][x][4 + i] for x in xs]; lo, hi = [a - b for a, b in zip(y, e)], [a + b for a, b in zip(y, e)]
        else: lo, hi = [P[s][x][2 + i][0] for x in xs], [P[s][x][2 + i][1] for x in xs]   # 95 % CI of the change
        ax.plot(xs, y, color=c, lw=lw, ls=ls, label=lbl, marker=mrk, ms=3.0, mec="white", mfc=c, mew=0.45, zorder=3)
        if STYLE == "bars":
            sh = 2 ** (0.08 if i == 1 else -0.08)   # the two series' bars sit slightly apart on the log axis
            ax.errorbar([x * sh for x in xs], y, yerr=[[a - b for a, b in zip(y, lo)], [b - a for a, b in zip(y, hi)]], fmt="none", ecolor=c,
                        elinewidth=0.75, capsize=1.3, capthick=0.75, zorder=2.5)
        else: ax.fill_between(xs, lo, hi, color=c, alpha=0.16, lw=0, zorder=1.5)
        if STYLE != "sd":   # interval includes 0: drawn hollow (filled = a change the interval separates from 0)
            weak = [k for k, x in enumerate(xs) if lo[k] <= 0 <= hi[k]]
            ax.plot([xs[k] for k in weak], [y[k] for k in weak], ls="none", marker=mrk, ms=3.0, mec=c, mfc="white", mew=0.7, zorder=3.5)
    ax.axhline(0, color="black", lw=0.6, zorder=2); ax.set_title(s, pad=1.5)
    ax.set_xscale("log", base=2); ax.minorticks_off(); ax.set_xticks(TK[s][0]); ax.set_xticklabels(TK[s][1])
    ax.set_ylim(*((-36, 20) if STYLE == "sd" else (-44, 22))); ax.set_yticks([-30, -20, -10, 0, 10, 20] if STYLE == "sd" else [-40, -20, 0, 20]); ax.tick_params(axis="both", length=1.8, pad=1.2, width=0.6)
    ax.grid(axis="y", ls="-", color="#e6e6e6", lw=0.5); ax.set_axisbelow(True)
axes[0].set_ylabel("Change in % (pp)", labelpad=1); fig.supxlabel("Fault-free period used for profiling", fontsize=8, y=0.06)
fig.subplots_adjust(left=0.15, right=0.985, bottom=0.25, top=0.81, wspace=0.18)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", bbox_to_anchor=(0.57, 1.0), ncol=2, frameon=False, handlelength=2.2, columnspacing=1.2, handletextpad=0.4, borderaxespad=0.1)
out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else HERE, "fig_08.pdf"); fig.savefig(out, bbox_inches="tight", pad_inches=0.01); print("saved", out)
fig.savefig(out[:-4] + ".png", bbox_inches="tight", pad_inches=0.01, dpi=300)   # preview for viewers that do not render the PDF

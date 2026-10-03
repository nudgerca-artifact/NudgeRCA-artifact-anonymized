"""§3.2 figure: the existing rule's flagged windows against the benchmark's incident windows.

Rows share one time axis (10 days; days without data are skipped and marked by an axis break):
  (a) Tomcat01 JVM used memory  -> value line, then the 10-min windows the existing rule flags
  (b) Tomcat01 cache memory     -> value line, then the 10-min windows the existing rule flags
      incident windows (30 min) of the benchmark, shared by both signals
The same block is drawn for a 3-hour span (zoom) with the range the rule treats as normal in each 10-min window, so that the reader sees why one signal is anomalous in every window and the other is not.

Outputs (PDF for LaTeX, PNG preview):
  fig_normal_period_10d   main block only (5.478 in wide)
  fig_normal_period_zoom  zoom block only
  fig_normal_period       main + zoom in one figure (the shaded column in the main block is the enlarged interval)
Inputs (cwd): metric_pair_series.json, metric_pair_bins.json, incident_windows.json, band_tables.json (prep_bands.py)
"""
import os, sys, json, datetime, zoneinfo, shutil, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.ticker as mt, matplotlib.patches as mp, matplotlib.transforms as mtr
from matplotlib.collections import BrokenBarHCollection
import figstyle; figstyle.apply(); C = figstyle.C
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
OUT = [os.path.join(os.path.dirname(HERE), "tracks")]   # run through run.sh: HERE is work/, the tracks go next to it
tz = zoneinfo.ZoneInfo("Asia/Shanghai")
ZOOM_START = datetime.datetime(2021, 3, 23, 22, 30, tzinfo=tz); ZOOM_HOURS = 3   # 3 h = 18 windows: one incident (23:00) and the cache-memory anomaly at 01:00, outside incidents
BAND_ALPHA = 0.45
SHARE_W = 0.075   # width of the share column relative to the time axis
MIN_BAR_PT = 0.7   # a run narrower than this (in points) is widened so it survives screen rendering; 30-min incident bars (0.69 pt) stay at true width

# ---------- data ----------
S = json.load(open("metric_pair_series.json")); bins_all = [int(b) for b in json.load(open("metric_pair_bins.json"))["bins_all"]]
bpos = {b: i for i, b in enumerate(bins_all)}; N = len(bins_all)
wins = [(int(s), int(e)) for s, e, _ in json.load(open("incident_windows.json"))]
bands = {k: {int(b): v for b, v in d.items()} for k, d in json.load(open("band_tables.json")).items()}
SIG = [  # key in series json, key in band json, label, divisor -> GB, letter
    dict(ser="heap", band="jvm", label="JVM used\nmemory (GB)", div=1e9),
    dict(ser="cache", band="cache", label="Cache\nmemory (GB)", div=1e3),   # raw values are MB (MEMTotalMem = 7,789)
]
day_start = {}
for b in bins_all:
    day_start.setdefault(datetime.datetime.fromtimestamp(b * 600, tz).date(), bpos[b])
gaps = [x for (d0, x0), (d1, x) in zip(list(day_start.items())[:-1], list(day_start.items())[1:]) if (d1 - d0).days > 1]

def pos_ts(ts):
    """timestamp -> x on the 10-day axis (bins of days without data are skipped)"""
    ts = np.asarray(ts, dtype=float); b = (ts // 600).astype(int); out = np.full(len(ts), np.nan)
    for i, (bb, t) in enumerate(zip(b, ts)):
        if bb in bpos: out[i] = bpos[bb] + (t % 600) / 600
        elif bb - 1 in bpos and t % 600 == 0: out[i] = bpos[bb - 1] + 1
    return out
def runs_from_bins(flag_bins, xmap):
    """merge consecutive flagged 10-min bins into [x0, x1) runs"""
    xs = sorted(xmap(b) for b in flag_bins if xmap(b) is not None); out = []
    for x in xs:
        if out and abs(x - out[-1][1]) < 1e-9: out[-1][1] = x + xmap.width
        else: out.append([x, x + xmap.width])
    return out

class Xmap10d:
    width = 1.0
    def __call__(self, b): return bpos.get(b)
    def ts(self, ts): return pos_ts(ts)
class Xmap8h:
    width = 1 / 6
    def __init__(self, t0): self.t0 = t0
    def __call__(self, b): return (b * 600 - self.t0) / 3600
    def ts(self, ts): return (np.asarray(ts, dtype=float) - self.t0) / 3600

# ---------- drawing ----------
def share_bar(ax, frac, color):
    """one contiguous bar: the row's share of the observed period in its colour, the rest in the 'outside' grey"""
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_collection(BrokenBarHCollection([(0, 1)], (0.2, 0.6), facecolors=C["outside"], linewidths=0, zorder=0.4))
    wmin = MIN_BAR_PT / (ax.get_window_extent().width * 72 / ax.figure.dpi)
    ax.add_collection(BrokenBarHCollection([(0, max(frac, wmin))], (0.2, 0.6), facecolors=color, linewidths=0, zorder=1))

def strip(ax, xr, color, xlim, background=None):
    """event strip: bars at 60 % of the row height; runs thinner than MIN_BAR_PT are widened.
    background: if given, the whole observed time is filled in that colour first, so that the bars' share reads as an area"""
    ax.set_ylim(0, 1); ax.set_xlim(*xlim); ax.set_yticks([]); ax.tick_params(axis="x", labelbottom=False, length=0)
    if background: ax.add_collection(BrokenBarHCollection([(xlim[0], xlim[1] - xlim[0])], (0.2, 0.6), facecolors=background, linewidths=0, zorder=0.4))
    for s in ("left", "right", "top"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(C["hair"]); ax.spines["bottom"].set_linewidth(0.5)
    if not xr: return
    w_pt_per_unit = ax.get_window_extent().width * 72 / ax.figure.dpi / (xlim[1] - xlim[0]); wmin = MIN_BAR_PT / w_pt_per_unit
    xr2 = []
    for x0, x1 in xr:
        if x1 - x0 < wmin: c = (x0 + x1) / 2; x0, x1 = c - wmin / 2, c + wmin / 2
        xr2.append((x0, x1 - x0))
    ax.add_collection(BrokenBarHCollection(xr2, (0.2, 0.6), facecolors=color, linewidths=0, antialiaseds=False))

def line_panel(ax, x, y, xlim, letter, ymax):
    ax.plot(x, y, color=C["line"], lw=0.5, solid_joinstyle="round", zorder=3)
    ax.set_xlim(*xlim); ax.set_ylim(0, ymax); ax.yaxis.set_major_locator(mt.MaxNLocator(nbins=4, integer=True))
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(C["spine"]); ax.spines["bottom"].set_color(C["hair"]); ax.spines["bottom"].set_linewidth(0.5)
    ax.tick_params(axis="x", labelbottom=False, length=0); ax.tick_params(axis="y", colors=C["spine"], labelcolor=C["line"])
    ax.text(0.004, 0.97, f"({letter})", transform=ax.transAxes, ha="left", va="top", fontsize=8, fontweight="bold", zorder=6)

def row_labels(fig, rows, gap_in=0.07):
    """horizontal row labels, right-aligned at a fixed x left of the widest y tick label of the block"""
    fig.canvas.draw(); inv = fig.transFigure.inverted(); xmin = min(ax.get_position().x0 for ax, _ in rows)
    for ax, _ in rows:
        for t in ax.get_yticklabels():
            if t.get_text(): xmin = min(xmin, inv.transform(t.get_window_extent().get_points())[0, 0])
    x = xmin - gap_in / fig.get_figwidth()
    for ax, lab in rows:
        bb = ax.get_position(); fig.text(x, (bb.y0 + bb.y1) / 2, lab, ha="right", va="center", fontsize=7.5, linespacing=1.25, color=C["line"])

def share_labels():
    obs = set()
    for b in bins_all: obs |= set(range(b * 600, b * 600 + 600, 60))
    cov = set()
    for st, en in wins: cov |= set(range(st - st % 60, en, 60))
    inc_share = len(cov & obs) / len(obs)
    return {k: len(set(S[k]["flags"])) / N for k in ("heap", "cache")}, inc_share
SHARE_ANOM, SHARE_INC = share_labels()

def draw_block(fig, spec, xmap, xlim, letters, zoom=None):
    """six rows: line a, strip a, spacer, line b, strip b, incident strip. Returns dict of axes."""
    gs = spec.subgridspec(6, 2, height_ratios=[1, 0.22, 0.10, 1, 0.22, 0.22], width_ratios=[1, SHARE_W], hspace=0, wspace=0.05)
    A = {}
    A["la"] = fig.add_subplot(gs[0, 0]); A["sa"] = fig.add_subplot(gs[1, 0]); A["lb"] = fig.add_subplot(gs[3, 0]); A["sb"] = fig.add_subplot(gs[4, 0]); A["si"] = fig.add_subplot(gs[5, 0])
    if not zoom:   # share of the whole period, as one contiguous bar per event row, so the proportion reads as an area
        for key, frac, col in (("sa", SHARE_ANOM["heap"], C["rule"]), ("sb", SHARE_ANOM["cache"], C["rule"]), ("si", SHARE_INC, C["incident"])):
            ax = fig.add_subplot(gs[{"sa": 1, "sb": 4, "si": 5}[key], 1]); share_bar(ax, frac, col); A["share_" + key] = ax
    fig.canvas.draw()
    for sig, la, sa, letter in [(SIG[0], A["la"], A["sa"], letters[0]), (SIG[1], A["lb"], A["sb"], letters[1])]:
        ts = np.array(S[sig["ser"]]["ts"], dtype=float); v = np.array(S[sig["ser"]]["v"], dtype=float) / sig["div"]
        if not zoom:
            line_panel(la, xmap.ts(ts), v, xlim, letter, v.max() * 1.22)
        else:
            sel = (ts >= zoom[0]) & (ts <= zoom[1]); ts, v = ts[sel], v[sel]
            # the range the rule treats as normal in each 10-min window: mean ± 3 sd of the preceding 5 min (sd floored as in the rule),
            # drawn as one stair-shaped corridor with an outline so that consecutive windows read as one moving range
            bt = bands[sig["band"]]; b0, b1 = zoom[0] // 600, zoom[1] // 600; edges = [xmap(b) for b in range(b0, b1 + 1)]
            lo = np.array([bt[b][0] - 3 * bt[b][1] if b in bt else np.nan for b in range(b0, b1)] + [np.nan]) / sig["div"]
            hi = np.array([bt[b][0] + 3 * bt[b][1] if b in bt else np.nan for b in range(b0, b1)] + [np.nan]) / sig["div"]
            lo[-1], hi[-1] = lo[-2], hi[-2]
            la.fill_between(edges, lo, hi, step="post", facecolor=C["band"], alpha=BAND_ALPHA, edgecolor=C["band_edge"], linewidth=0.4, zorder=1)
            la.plot(xmap.ts(ts), v, color=C["line"], lw=0.5, marker="o", ms=2.0, mew=0, zorder=3)
            ymin_, ymax_ = np.nanmin([v.min(), np.nanmin(lo)]), np.nanmax([v.max(), np.nanmax(hi)]); r = ymax_ - ymin_
            line_panel(la, [], [], xlim, letter, 1); la.set_ylim(ymin_ - 0.10 * r, ymax_ + 0.36 * r); la.yaxis.set_major_locator(mt.MaxNLocator(nbins=4))
        strip(sa, runs_from_bins(S[sig["ser"]]["flags"], xmap), C["rule"], xlim)
    # incident windows: exact [start, end] in continuous time
    xr = []
    for s, e in wins:
        x0, x1 = xmap.ts([s, e])
        if zoom and (e < zoom[0] or s > zoom[1]): continue
        if np.isnan(x0) or np.isnan(x1): continue
        xr.append([x0, x1])
    strip(A["si"], xr, C["incident"], xlim, background=C["outside"])
    A["si"].spines["bottom"].set_color(C["spine"]); A["si"].spines["bottom"].set_linewidth(0.6); A["si"].tick_params(axis="x", labelbottom=True, length=2.2, color=C["spine"])
    row_labels(fig, [(A["la"], SIG[0]["label"]), (A["sa"], "Anomalies by 3σ"), (A["lb"], SIG[1]["label"]), (A["sb"], "Anomalies by 3σ"), (A["si"], "Incidents")])
    if not zoom:
        bb = A["share_sa"].get_position(); fig.text((bb.x0 + bb.x1) / 2, bb.y1 + 0.012, "share of\n10 days", ha="center", va="bottom", fontsize=7, linespacing=1.2, color=C["line"])
    return A

def incident_legend(A):
    A["lb"].legend(handles=[mp.Patch(facecolor=C["incident"], edgecolor="none"), mp.Patch(facecolor=C["outside"], edgecolor="none")], labels=["incident window (30 min)", "outside incident windows"], loc="upper left", bbox_to_anchor=(0.035, 1.0), ncol=2, columnspacing=1.6, handlelength=1.6, handleheight=0.8, borderaxespad=0.3, borderpad=0.0)

def finish_10d(fig, A):
    incident_legend(A)
    ax = A["si"]; ax.set_xticks(list(day_start.values())); ax.set_xticklabels([d.strftime("%b %-d") for d in day_start])
    for a in (A["la"], A["lb"]):
        for x in list(day_start.values())[1:]: a.axvline(x, color=C["daygrid"], lw=0.4, zorder=0)
    # days without data: a light rule through every row and an axis break on the date axis
    for g in gaps:
        for a in A.values(): a.axvline(g - 0.5, color=C["gap"], lw=0.5, zorder=2)
        tr = mtr.blended_transform_factory(ax.transData, ax.transAxes); d = 3.5; o = 3.0
        ax.add_patch(mp.Rectangle((g - 0.5 - d - o, -0.28), 2 * (d + o), 0.56, transform=tr, facecolor="white", edgecolor="none", zorder=10, clip_on=False))
        for off in (-o, o): ax.add_line(plt.Line2D([g - 0.5 + off - d, g - 0.5 + off + d], [-0.22, 0.22], transform=tr, color=C["spine"], lw=0.6, zorder=11, clip_on=False))

def finish_zoom(fig, A, t0, hours):
    ax = A["si"]; t1 = t0 + hours * 3600; ticks = [t for t in range(-(-t0 // 1800) * 1800, t1 + 1, 1800)]
    ax.set_xticks([(t - t0) / 3600 for t in ticks]); ax.set_xticklabels([datetime.datetime.fromtimestamp(t, tz).strftime("%H:%M") for t in ticks])
    for a in (A["la"], A["lb"]):
        for t in ticks:
            if t % 3600 == 0: a.axvline((t - t0) / 3600, color=C["daygrid"], lw=0.4, zorder=0)
    A["lb"].legend(handles=[mp.Patch(facecolor=C["band"], alpha=BAND_ALPHA, edgecolor=C["band_edge"], linewidth=0.4)], labels=["range the rule treats as normal:\nmean ± 3σ of the preceding 5 min"], loc="upper right", handlelength=1.6, handleheight=1.6, borderaxespad=0.3, borderpad=0.0, labelspacing=0.2)

def zoom_shade(A, x0, x1, label):
    """mark the enlarged interval as one light column behind every row (no box, no connectors), named in a one-line legend"""
    for ax in A.values(): ax.axvspan(x0, x1, facecolor=C["shade"], edgecolor="none", lw=0, zorder=0.5)
    A["la"].legend(handles=[mp.Patch(facecolor=C["shade"], edgecolor="none")], labels=[label], loc="upper right", handlelength=1.6, handleheight=0.8, borderaxespad=0.3, borderpad=0.0)

def save(fig, name):
    for d in OUT:
        os.makedirs(d, exist_ok=True); fig.savefig(os.path.join(d, name + ".pdf")); fig.savefig(os.path.join(d, name + ".png"), dpi=300)
    print("saved", name)

t0 = int(ZOOM_START.timestamp()); t1 = t0 + ZOOM_HOURS * 3600; W = figstyle.TEXTWIDTH_IN; LEFT = 0.155
# 1) 10-day block
fig = plt.figure(figsize=(W, 2.75)); gs = fig.add_gridspec(1, 1, left=LEFT, right=0.995, top=0.985, bottom=0.075)
A = draw_block(fig, gs[0], Xmap10d(), (-0.5, N - 0.5), ("a", "b")); finish_10d(fig, A); zoom_shade(A, *pos_ts([t0, t1]), "enlarged in the next figure"); save(fig, "fig_normal_period_10d"); plt.close(fig)
# 2) 8-hour block
fig = plt.figure(figsize=(W, 2.45)); gs = fig.add_gridspec(1, 1, left=LEFT, right=0.995, top=0.985, bottom=0.085)
A = draw_block(fig, gs[0], Xmap8h(t0), (0, ZOOM_HOURS), ("a", "b"), zoom=(t0, t1)); finish_zoom(fig, A, t0, ZOOM_HOURS); save(fig, "fig_normal_period_zoom"); plt.close(fig)
# 3) both in one figure
fig = plt.figure(figsize=(W, 4.9)); gs = fig.add_gridspec(3, 1, height_ratios=[2.55, 0.34, 2.2], left=LEFT, right=0.995, top=0.99, bottom=0.045, hspace=0)
A1 = draw_block(fig, gs[0], Xmap10d(), (-0.5, N - 0.5), ("a", "b")); finish_10d(fig, A1)
A2 = draw_block(fig, gs[2], Xmap8h(t0), (0, ZOOM_HOURS), ("c", "d"), zoom=(t0, t1)); finish_zoom(fig, A2, t0, ZOOM_HOURS)
zoom_shade(A1, *pos_ts([t0, t1]), "enlarged in (c) and (d)"); save(fig, "fig_normal_period"); plt.close(fig)
# counts for the caption
inc = set(); pad = set()
for s, e in wins: inc |= set(range(s // 600, e // 600 + 1)); pad |= set(range((s - 300) // 600, (e + 300) // 600 + 1))
nb = {b for b in bins_all if b not in pad}
for sig in SIG:
    fl = set(S[sig["ser"]]["flags"]); print(sig["ser"], "flagged windows", len(fl), "of", N, "| outside incidents", len(fl & nb), "of", len(nb), f"({len(fl & nb)/len(nb):.1%})", "| in zoom", sum(1 for b in range(t0//600, t1//600) if b in fl), "of", ZOOM_HOURS*6)

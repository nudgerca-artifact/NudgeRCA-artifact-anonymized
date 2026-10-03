"""Shared figure style of the paper (acmart, acmsmall).

- Text width of acmsmall is 395.8 pt = 5.478 in; figures are drawn at that width so the
  fonts land at their nominal size (no scaling in \\includegraphics).
- Body font of acmart is Linux Libertine; figures use the same face.
- Palette: the two event colours pass the dataviz validator (lightness band, chroma,
  CVD separation, 3:1 contrast on white). The band colour is a wash, not an identity colour.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
TEXTWIDTH_IN = 5.478
def apply():
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Linux Libertine O", "TeX Gyre Termes", "Nimbus Roman", "DejaVu Serif"],
        "mathtext.fontset": "custom", "mathtext.rm": "Linux Libertine O", "mathtext.it": "Linux Libertine O:italic", "mathtext.bf": "Linux Libertine O:bold",
        "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5, "xtick.major.size": 2.2, "ytick.major.size": 2.2,
        "xtick.direction": "out", "ytick.direction": "out", "axes.grid": False, "legend.frameon": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "figure.dpi": 150,
    })
C = {
    "line": "#1A1A1A",      # raw value
    "rule": "#A5402A",      # windows flagged by the existing rule
    "incident": "#B48A1C",  # incident windows (benchmark label)
    "band": "#B39BA5", "band_edge": "#8E7580",   # the range the rule treats as normal (fill at alpha 0.45, thin outline)
    "spine": "#333333", "hair": "#D9D9D9", "daygrid": "#EFEFEF", "gap": "#BDBDBD", "shade": "#DEDEDE", "outside": "#BEBEBE", "text2": "#555555",
}
def subcap(ax, text, y=-0.30):
    ax.text(0.5, y, text, transform=ax.transAxes, ha="center", va="top", fontsize=8)

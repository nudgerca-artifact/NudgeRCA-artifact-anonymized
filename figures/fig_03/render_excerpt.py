"""Render an excerpt of the selected job's raw reasoning as a LaTeX box (figure (b)). Usage: python3 render_excerpt.py <job> [max lines]
Grey = procedural steps (scan, propagation); highlight = the final decision sentence (magnitude-based rationale). The excerpt is chosen by hand as line indices in data/excerpt_<job>.json."""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "common", "section3"))
import loaders as L
job = sys.argv[1]
local = os.path.join(HERE, "data", "trajectories", f"{job}.json")   # the two trajectories of the figure are kept here; any other job is read from ../common/section3
t = {x["job"]: x for x in L.load_v4_trajectories(glob_dir=os.path.dirname(local) if os.path.exists(local) else None)}[job]
spec_p = os.path.join(HERE, "data", f"excerpt_{job}.json")
paras = [p.strip() for p in t["think"].split("\n") if p.strip()]
if not os.path.exists(spec_p):
    json.dump(dict(job=job, gt=t["gt_comp"], top1=t["top1"], grey=[], highlight=[], paragraphs=paras), open(spec_p, "w"), indent=1, ensure_ascii=False)
    print(f"wrote {spec_p} with {len(paras)} paragraphs; fill grey/highlight indices then rerun"); sys.exit(0)
spec = json.load(open(spec_p))
def esc(s): return s.replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#").replace("$", "\\$")
L_ = ["\\begin{tcolorbox}[colback=white, boxrule=0.4pt, fontupper=\\scriptsize, title={Case " + esc(t["uuid"]) + f", sample {t['sample']}: GT = " + esc(t["gt_comp"]) + ", answer = " + esc(t["top1"]) + "}]"]
for i in spec["grey"]: L_.append("\\textcolor{gray}{" + esc(paras[i]) + "}\\par")
for i in spec["highlight"]: L_.append("\\colorbox{yellow!30}{\\parbox{\\linewidth}{" + esc(paras[i]) + "}}\\par")
L_.append("\\end{tcolorbox}")
open(os.path.join(HERE, f"excerpt_{job}.tex"), "w").write("\n".join(L_) + "\n"); print("wrote tex")

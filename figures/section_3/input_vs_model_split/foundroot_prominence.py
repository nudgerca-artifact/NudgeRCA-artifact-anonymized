"""Section 3, a model trained on the procedure: whether FoundRoot-14B (SFT and RL on the diagnostic procedure) answers the component
with the most anomalous metrics in the authors' released input (the most prominent candidate), split by whether that component is
the root cause. The untrained Qwen3-4B on the same input (8 samples per case) is counted alongside.
Input: baselines/foundroot/{inputs/authors-matched-55.jsonl, results/foundroot-14b/authors-55.jsonl,
untrained-on-authors-input/results/base__{bank,telecom}.jsonl}: the 55 incidents of the authors' data that are also OpenRCA bank (49)
and telecom (6) incidents; 24 ask for the component, 21 have a single most-metrics component, FoundRoot ranked 18 of them."""
import sys, json, collections
import os
ART=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..')); F=f'{ART}/baselines/foundroot'
sys.path.insert(0,f'{ART}/nudgerca/inference')
from score_openrca_corrected import parse_answer, comp_match
inputs={(r['case_idx'],r['_task_index']):r for r in map(json.loads,open(f'{F}/inputs/authors-matched-55.jsonl'))}
fr={(r['case_id'],r['task_index']):r for r in map(json.loads,open(f'{F}/results/foundroot-14b/authors-55.jsonl'))}
base={}
for ds in ['bank','telecom']:
    for r in map(json.loads,open(f'{F}/untrained-on-authors-input/results/base__{ds}.jsonl')): base[(r['case_id'],r['task_index'])]=r
rows=[]
for key,inp in inputs.items():
    if 'component' not in inp['_asks']: continue
    cat=inp['_catalog']; gts=inp['_gt']['components']
    cnt=collections.Counter(m.split('##')[0] for m in inp['metrics'] if m.split('##')[0] in cat)
    top=max(cnt.values()); tops=[c for c,v in cnt.items() if v==top]
    if len(tops)!=1: continue
    prom=tops[0]; gt_is_prom=any(comp_match(prom,g) for g in gts)
    rank=fr.get(key,{}).get('foundroot',{}).get('rank',[]); fr_top=rank[0] if rank else None
    preds=[]
    for out in base.get(key,{}).get('outputs',[]):
        a=parse_answer(out); a=a[0] if isinstance(a,list) and a else a
        preds.append((a or {}).get('component','') if isinstance(a,dict) else '')
    rows.append((gt_is_prom, fr_top and comp_match(fr_top,prom), fr_top and any(comp_match(fr_top,g) for g in gts), fr_top is not None,
                 [comp_match(p,prom) for p in preds if p], [any(comp_match(p,g) for g in gts) for p in preds if p]))
def rep(rs,label):
    frn=sum(1 for r in rs if r[3]); ff=sum(1 for r in rs if r[1]); fc=sum(1 for r in rs if r[2])
    bf=sum(sum(r[4]) for r in rs); bc=sum(sum(r[5]) for r in rs); bn=sum(len(r[4]) for r in rs)
    print(f"[{label}] cases={len(rs)} | FoundRoot-14B: follow {ff}/{frn}, correct {fc}/{frn} | untrained Qwen3-4B: follow {bf}/{bn}, correct {bc}/{bn}")
rep(rows,'single most-metrics component'); rep([r for r in rows if r[0]],'  = GT'); rep([r for r in rows if not r[0]],'  != GT')

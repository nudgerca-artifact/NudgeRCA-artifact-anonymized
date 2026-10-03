"""Table tab:behavior split: the 640 judged trajectories (behavior_judge) grouped by whether the root-cause component is in the
top group of the input by summed deviation (sum_z), with behaviour rates and accuracy per group.
Input: ../behavior_judge/data/judge_inputs/chunk_*.md (case header: ground truth, per-entity sum_z / max_z) and ../behavior_judge/data/adjudicated.jsonl.
The prompt caps z at 30, so the top sum_z is tied among 4.6 entities per case on average; the split is "in the tied top group or not".
Counting rule: of the 81 judged cases, the one whose final ranked answer cannot be read in a trajectory (openrca_bank_1615319040_62) is left out,
which leaves 80 cases and 640 trajectories."""
import re, json, glob, collections, os
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','behavior_judge','data')
adj={r['job']:r for r in (json.loads(l) for l in open(f'{D}/adjudicated.jsonl'))}
cases={}
for f in sorted(glob.glob(f'{D}/judge_inputs/chunk_*.md')):
    cur=None; mode=None
    for line in open(f,encoding='utf-8'):
        line=line.rstrip('\n')
        m=re.match(r'^### CASE (\S+)',line)
        if m: cur={'id':m.group(1),'gt':None,'ents':[],'trajs':[]}; cases[cur['id']]=cur; mode='hdr'; continue
        if cur is None: continue
        m=re.match(r'^Ground truth .*?component=([^,\s]+)',line)
        if m: cur['gt']=m.group(1); continue
        m=re.match(r'^- (\S+): sum_z=(\d+), max_z=(\d+)',line)
        if m and mode=='hdr': cur['ents'].append((m.group(1),int(m.group(2)),int(m.group(3)))); continue
        m=re.match(r'^#### TRAJECTORY job=(\S+) \(correct=(yes|no)\)',line)
        if m: cur['trajs'].append({'job':m.group(1),'correct':m.group(2),'pred':None}); mode='traj'; continue
        if mode=='traj' and cur['trajs'] and cur['trajs'][-1]['pred'] is None:
            m=re.match(r'^\s*1\.\s*([^:\s]+)',line)
            if m: cur['trajs'][-1]['pred']=m.group(1)
DROP={'openrca_bank_1615319040_62'}
cases={k:v for k,v in cases.items() if k not in DROP}
def group(c):
    top=max(e[1] for e in c['ents']); tops={e[0] for e in c['ents'] if e[1]==top}
    return 'gt_in_top' if c['gt'] in tops else 'gt_below_top'
G=collections.defaultdict(list)
for c in cases.values(): G[group(c)].append(c)
for g,cs in G.items():
    trs=[t for c in cs for t in c['trajs']]
    won=sum(adj[t['job']]['won'] for t in trs)
    print(f"[{g}] cases={len(cs)} trajs={len(trs)} success={won}/{len(trs)} ({won/len(trs)*100:.0f}%)")
    for k in ['q4_mag_rationale','m2_self_contra','q3_ungrounded','q5_causal_chain','f_gt_considered']:
        xs=[adj[t['job']][k] for t in trs]; print(f"   {k}: {sum(x=='yes' for x in xs)/len(xs)*100:.0f}%")
ties=[len({e[0] for e in c['ents'] if e[1]==max(x[1] for x in c['ents'])}) for c in cases.values()]
print('tied-at-top per case: mean %.1f' % (sum(ties)/len(ties)))

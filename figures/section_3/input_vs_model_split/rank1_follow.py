"""Section 3, the second analysis of the cause-selection subsection: on the input that orders candidates by how rarely their signals
exceed the threshold in fault-free windows, how often the untrained Qwen3-4B answers the first-listed candidate, split by whether that
candidate is the root cause. Cases that ask for the component (telecom 10, bank 25, market 35, aiops 159 = 229), 8 samples each.
Input: the evaluation renders (nudgerca/preprocessing/rendered-inputs/eval/) and the untrained outputs (nudgerca/inference/outputs/base/)."""
import sys, json, re, collections
import os
ART=os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..'))
sys.path.insert(0, f'{ART}/nudgerca/inference')
from score_openrca_corrected import parse_answer, comp_match
pairs={ds:(f'{ART}/nudgerca/preprocessing/rendered-inputs/eval/{ds}.jsonl',f'{ART}/nudgerca/inference/outputs/base/{ds}.jsonl') for ds in ['telecom','bank','market','aiops']}
tot=collections.Counter()
for ds,(pf,sf) in pairs.items():
    prompts={(r['case_id'],r['task_index']):r for r in map(json.loads,open(pf))}
    st=collections.Counter()
    for o in map(json.loads,open(sf)):
        asks=o['asks'] if isinstance(o['asks'],list) else eval(str(o['asks']))
        if 'component' not in asks: continue
        gt=o['gt'] if isinstance(o['gt'],dict) else eval(str(o['gt']))
        p=prompts[(o['case_id'],o['task_index'])]
        rank1=re.findall(r'^### (\S+) \(',p['prompt'],re.M)[0]; gts=gt['components']
        key='r1=GT' if any(comp_match(rank1,g) for g in gts) else 'r1!=GT'
        st[('cases',key)]+=1
        for out in o['outputs']:
            x=parse_answer(out); x=x[0] if isinstance(x,list) and x else x
            pred=(x or {}).get('component','') if isinstance(x,dict) else ''
            st[(key,'n')]+=1; st[(key,'follow')]+=bool(pred) and comp_match(pred,rank1); st[(key,'correct')]+=bool(pred) and any(comp_match(pred,g) for g in gts)
    print(f"== {ds}: cases r1=GT {st[('cases','r1=GT')]} / r1!=GT {st[('cases','r1!=GT')]}")
    for key in ['r1=GT','r1!=GT']:
        n=st[(key,'n')]
        if n: print(f"   {key}: trajs={n} follow-rank1={st[(key,'follow')]/n*100:.0f}% correct={st[(key,'correct')]/n*100:.0f}%")
    for k,v in st.items():
        if isinstance(k,tuple): tot[k]+=v
print('== total'); 
for key in ['r1=GT','r1!=GT']:
    n=tot[(key,'n')]; print(f"   {key}: cases={tot[('cases',key)]} trajs={n} follow-rank1={tot[(key,'follow')]/n*100:.0f}% correct={tot[(key,'correct')]/n*100:.0f}%")

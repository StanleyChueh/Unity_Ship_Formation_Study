import json,glob,os,sys
import numpy as np
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from pilot import iou,cond,ROOT
def run(d):
    job=json.load(open(d+'/job.json'));out=[];prev={}
    if job.get('detector')!='best_realistic_v2.pt': return None
    for line in open(d+'/steps.jsonl'):
        r=json.loads(line)
        if r['t']<0: continue
        shift=r['height']-1-job.get('id_box_encoded_y_origin',359)
        for side,key in (('Left','left_boxes'),('Right','right_boxes')):
            gts=[(b['x'],b['y']+shift,b['x']+b['w'],b['y']+shift+b['h'],b['id']) for b in r[key]]
            lead=[g for g in gts if g[4]==1]
            if not lead: prev.pop(side,None); continue
            L=lead[0];cy=(L[1]+L[3])/2;cx=(L[0]+L[2])/2;h=L[3]-L[1]
            p=prev.get(side);prev[side]=(cx,cy)
            if p is None: continue
            vy=abs(cy-p[1]);vx=abs(cx-p[0])
            dets=[d_ for d_ in r['raw_detections'].get(side+'Front',[]) if d_[5]==0]
            ok=any(iou(d_,L)>=0.3 for d_ in dets); wrong=any(iou(d_,L)<0.3 for d_ in dets)
            out.append((vy,vx,h,ok,wrong))
    return cond(job),np.array(out,float)
ds=[d for d in glob.glob(ROOT+'/*/runs/*') if os.path.exists(d+'/steps.jsonl')]
with Pool(12) as p: res=[r for r in p.map(run,ds,chunksize=4) if r]
A=np.vstack([r[1] for r in res if len(r[1])]);C=np.concatenate([[r[0]]*len(r[1]) for r in res if len(r[1])])
print('frames',len(A))
for c in sorted(set(C)):
    v=A[C==c,0];print(f'{c:12s} vertical box speed px/step: median {np.median(v):5.1f}  p95 {np.percentile(v,95):6.1f}   horizontal median {np.median(A[C==c,1]):4.1f}')
print('\nbin of |dy| (px per 0.1 s) -> leader missed %, false-leader-box %, n   [all conditions, v2 detector]')
for lo,hi in [(0,2),(2,5),(5,10),(10,20),(20,40),(40,1e9)]:
    m=(A[:,0]>=lo)&(A[:,0]<hi)
    if m.sum(): print(f'  {lo:3.0f}-{hi:<5.0f}: miss {100*(1-A[m,3].mean()):5.2f}%   false {100*A[m,4].mean():5.2f}%   n={m.sum()}')
m=C=='huge_waves'
print('huge waves only:')
for lo,hi in [(0,5),(5,10),(10,20),(20,40),(40,1e9)]:
    k=m&(A[:,0]>=lo)&(A[:,0]<hi)
    if k.sum(): print(f'  {lo:3.0f}-{hi:<5.0f}: miss {100*(1-A[k,3].mean()):5.2f}%   false {100*A[k,4].mean():5.2f}%   n={k.sum()}')

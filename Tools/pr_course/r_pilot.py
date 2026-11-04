import json,glob,os,sys
import numpy as np
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from pilot import iou,cond,ROOT
def run(d):
    job=json.load(open(d+'/job.json'));out=[]
    if job.get('detector')!='best_realistic_v2.pt': return None
    for line in open(d+'/steps.jsonl'):
        r=json.loads(line)
        if r['t']<0: continue
        shift=r['height']-1-job.get('id_box_encoded_y_origin',359)
        for side,key in (('Left','left_boxes'),('Right','right_boxes')):
            lead=[(b['x'],b['y']+shift,b['x']+b['w'],b['y']+shift+b['h']) for b in r[key] if b['id']==1]
            if not lead: continue
            L=lead[0]
            for d_ in r['raw_detections'].get(side+'Front',[]):
                if d_[5]==0 and iou(d_,L)>=0.3:
                    H=L[3]-L[1]
                    out.append((d_[4],((d_[0]+d_[2])-(L[0]+L[2]))/2/H,((d_[1]+d_[3])-(L[1]+L[3]))/2/H))  # residual in units of box height
    return cond(job),np.array(out)
ds=[d for d in glob.glob(ROOT+'/*/runs/*') if os.path.exists(d+'/steps.jsonl')]
with Pool(12) as p: res=[r for r in p.map(run,ds,chunksize=4) if r and len(r[1])]
for name,sel in [('all',lambda c:True),('huge_waves',lambda c:c=='huge_waves'),('night+rain',lambda c:c=='night+rain')]:
    A=np.vstack([r[1] for r in res if sel(r[0])])
    print(f'\n{name}: n={len(A)}   conf bin -> MLE var(cx), var(cy) [box-height units^2], ratio to bin0; drone rule (0.5/s)^2 ratio')
    bins=[0.25,0.4,0.55,0.7,0.8,0.9,1.01];base=None
    for lo,hi in zip(bins,bins[1:]):
        m=(A[:,0]>=lo)&(A[:,0]<hi)
        if m.sum()<50: continue
        vx=np.mean(A[m,1]**2);vy=np.mean(A[m,2]**2);s=A[m,0].mean()   # zero-mean MLE of variance
        if base is None: base=(vy,s)
        print(f'  {lo:.2f}-{hi:.2f} n={m.sum():6d}  var_x={vx:.4f} var_y={vy:.4f}  ratio_y={vy/base[0]:.2f}  rule={(base[1]/s)**2:.2f}  mean_y={A[m,2].mean():+.3f}')

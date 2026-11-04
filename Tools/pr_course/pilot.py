import json,sys,glob,os
from multiprocessing import Pool
from collections import Counter
ROOT='/home/stanley/Github/Unity_Ship_Formation_Study/Experiments/KalmanStudy/robust_evaluation'
def iou(a,b):
    x0=max(a[0],b[0]);y0=max(a[1],b[1]);x1=min(a[2],b[2]);y1=min(a[3],b[3])
    i=max(0,x1-x0)*max(0,y1-y0);u=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i
    return i/u if u>0 else 0
def cond(job):
    if job.get('dark') and job.get('rain'): return 'night+rain'
    if job.get('dark'): return 'night'
    if job.get('rain'): return 'rain'
    if job.get('fog'): return 'fog'
    if job.get('sea',0)>=2.5: return 'huge_waves'
    return 'clear'
def run(d):
    try:
        job=json.load(open(d+'/job.json'))
        c=Counter();
        for line in open(d+'/steps.jsonl'):
            r=json.loads(line)
            if r['t']<0: continue
            shift=r['height']-1-job.get('id_box_encoded_y_origin',359)
            for side,key in (('Left','left_boxes'),('Right','right_boxes')):
                gts=[(b['x'],b['y']+shift,b['x']+b['w'],b['y']+shift+b['h'],b['id']) for b in r[key]]
                lead=[g for g in gts if g[4]==1]
                dets=r['raw_detections'].get(side+'Front',[])
                c['gt_visible']+=bool(lead)
                c['frames']+=1
                hit=False
                for det in dets:
                    best=max(gts,key=lambda g:iou(det,g),default=None)
                    v=iou(det,best) if best else 0
                    lab="leader" if (v>=0.3 and best[4]==1) else ("other_boat" if v>=0.3 else "background"); c["yolo%d_%s"%(int(det[5]),lab)]+=1
                    if lab=="leader": hit=True
                c['ndet']+=len(dets)
                c['miss']+= bool(lead) and not hit
                c['multi']+= len(dets)>1
        return cond(job),job.get('detector','?'),c
    except Exception as e:
        return None
if __name__=='__main__':
    ds=[d for d in glob.glob(ROOT+'/*/runs/*') if os.path.exists(d+'/steps.jsonl')]
    tot={}
    with Pool(12) as p:
        for res in p.imap_unordered(run,ds,chunksize=4):
            if not res: continue
            k=(res[0],res[1]); tot.setdefault(k,Counter()).update(res[2]); tot.setdefault(k,Counter())['runs']+=1
    for k,c in sorted(tot.items()):
        print(k,dict(c))

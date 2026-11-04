import json,glob,os,math,sys
import numpy as np
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__))
from pilot import iou,cond,ROOT
def run(d):
    job=json.load(open(d+'/job.json'));X=[];prev={}
    for line in open(d+'/steps.jsonl'):
        r=json.loads(line)
        if r['t']<0: continue
        shift=r['height']-1-job.get('id_box_encoded_y_origin',359)
        for side,key in (('Left','left_boxes'),('Right','right_boxes')):
            gts=[(b['x'],b['y']+shift,b['x']+b['w'],b['y']+shift+b['h'],b['id']) for b in r[key]]
            dets=r['raw_detections'].get(side+'Front',[]);n=len(dets)
            p=prev.get(side)
            for det in dets:
                best=max(gts,key=lambda g:iou(det,g),default=None);v=iou(det,best) if best else 0
                y=0 if (v>=0.3 and best[4]==1) else (1 if v>=0.3 else 2)
                w=det[2]-det[0];h=det[3]-det[1];cx=(det[0]+det[2])/2/1280;cy=(det[1]+det[3])/2/720
                dprev=math.hypot(cx-p[0],cy-p[1]) if p else 0.5
                darea=math.log(max(w*h,1)/p[2]) if p else 0
                X.append([det[4],det[5],cx,cy,math.log(max(w,1)),math.log(max(h,1)),math.log(max(w,1)/max(h,1)),n,dprev,darea,y])
            lead=[d_ for d_ in dets if d_[5]==0]
            if lead:
                b=max(lead,key=lambda q:q[4]);prev[side]=((b[0]+b[2])/2/1280,(b[1]+b[3])/2/720,max((b[2]-b[0])*(b[3]-b[1]),1))
    return cond(job),job.get('detector','old'),job['seed'],np.array(X)
if __name__=='__main__':
    ds=[d for d in glob.glob(ROOT+'/*/runs/*') if os.path.exists(d+'/steps.jsonl')]
    with Pool(12) as pool: res=[r for r in pool.map(run,ds,chunksize=4) if len(r[3])]
    np.save(sys.argv[1] if len(sys.argv)>1 else 'pilot_data.npy',np.array(res,dtype=object),allow_pickle=True)
    # Evaluation (numpy-only Gaussian MLE + Bayes rule) lives in pilot_eval.py

#!/usr/bin/env python3
"""Compare the original and adapted checkpoints without training or deployment."""
import hashlib
import json
from pathlib import Path
import ultralytics
from ultralytics import YOLO

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'Documentation/RealisticModelEvaluation'


def main():
    OUT.mkdir(exist_ok=True)
    summary={'ultralytics':ultralytics.__version__,'imgsz':640,'models':{}}
    for tag,filename in [('old','best_v2.pt'),('adapted','best_realisitc.pt')]:
        path=ROOT/filename
        model=YOLO(str(path))
        assert model.names=={0:'leader',1:'follower'},model.names
        info={'filename':filename,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'splits':{}}
        for split,yaml in [('test','data.yaml'),('legacy_val','legacy_val.yaml')]:
            metrics=model.val(data=str(ROOT/'Datasets/boat_adaptation_v1'/yaml),
                              split='test' if split=='test' else 'val',
                              imgsz=640,batch=16,device=0,workers=2,plots=True,
                              project=str(OUT/'detection'),name=tag+'_'+split,
                              exist_ok=False,verbose=False)
            per_class={}
            for index,cls in enumerate(metrics.box.ap_class_index):
                per_class[model.names[int(cls)]]={
                    'precision':float(metrics.box.p[index]),'recall':float(metrics.box.r[index]),
                    'map50':float(metrics.box.ap50[index]),'map50_95':float(metrics.box.ap[index].mean())}
            info['splits'][split]={'metrics':{k:float(v) for k,v in metrics.results_dict.items()},
                                  'per_class':per_class,'speed_ms':metrics.speed,
                                  'confusion_matrix_predicted_rows_true_columns':metrics.confusion_matrix.matrix.tolist(),
                                  'output':str(metrics.save_dir)}
            print(tag,split,json.dumps(info['splits'][split]['metrics']),flush=True)
        summary['models'][tag]=info
        (OUT/'detection-summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()

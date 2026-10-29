#!/usr/bin/env python3
"""Isolated model A/B test using the real Python formation controller.

Unity/receiver instrumentation exists only in the scratch project. Exact JPEG
hashes pair selected targets with same-frame scene-identity masks for evaluation.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess

from generate_dataset import ROOT, UNITY_DEFAULT, clone_project

WORK=Path('/tmp/usv-model-comparison')
OUT=ROOT/'Documentation/RealisticModelEvaluation/live'
PYTHON='/home/stanley/miniconda3/envs/unity_boat/bin/python'


def build():
    project=clone_project(WORK)
    shutil.copy2(Path(__file__).with_name('USVModelTestRig.cs'),project/'Assets/USVModelTestRig.cs')
    sender=project/'Assets/Sender.cs'
    text=sender.read_text();anchor='            writer.Write(targetWidth);'
    assert text.count(anchor)==1
    sender.write_text(text.replace(anchor,'            USVModelTestRig.RecordFrame(cam, jpgBytes, targetWidth, targetHeight);\n'+anchor))
    binary=WORK/'build/usv_model_test.x86_64';binary.parent.mkdir(exist_ok=True)
    env=os.environ.copy();env['USV_DATASET_BUILD']=str(binary)
    log=WORK/'build.log'
    result=subprocess.run([str(UNITY_DEFAULT),'-batchmode','-projectPath',str(project),'-buildTarget','Linux64',
                           '-executeMethod','USVDatasetBuild.Build','-logFile',str(log)],env=env,
                          stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    lines=log.read_text(errors='replace').splitlines()
    errors=[s for s in lines if 'error CS' in s or 'Shader error' in s]
    if result.returncode or errors or not any('[DatasetBuild] Succeeded' in s for s in lines):
        raise RuntimeError(f'Build failed: {errors}; log {log}')
    print('Isolated build passed.',flush=True)


def instrument_python(project,output,model,radius):
    config=(ROOT/'Assets/usv/config.py').read_text()
    values=dict(PORT_LEFT_RX=47310,PORT_LEFT_TX=47300,PORT_RIGHT_RX=47311,PORT_RIGHT_TX=47301,
                LEADER_RX=47302,LEADER_TX=47312,LEADER_AUTO_TRAJECTORY_TX_PORT=47302,WAVE_CONTROL_PORT=47303,
                PORT_LEFT_FRONT_CAM=44998,PORT_RIGHT_FRONT_CAM=44999,PORT_LEFT_SIDE_CAM=45000,PORT_RIGHT_SIDE_CAM=45001,
                SHOW_WINDOW=False,YOLO_MODEL_PATH=str(model),LEADER_TRAJECTORY_CIRCLE_RADIUS=radius)
    for key,value in values.items():
        config,n=re.subn(r'^'+key+r'\s*=.*$',key+' = '+repr(value),config,flags=re.M)
        assert n==1,key
    (project/'Assets/usv/config.py').write_text(config)
    app=(ROOT/'Assets/usv/app.py').read_text().replace('int(LEADER_RX), 5065','int(LEADER_RX), 47300')
    (project/'Assets/usv/app.py').write_text(app)
    vision=(ROOT/'Assets/usv/vision.py').read_text()
    prefix='import hashlib, json, os\n_payload_hashes = {}\n_audit_log = open(os.environ["USV_SELECTION_AUDIT"], "w", buffering=1)\n'
    anchor='                with frame_lock:\n                    latest_frames[stream_name] = frame'
    assert vision.count(anchor)==1
    vision=vision.replace(anchor,'                _payload_hashes[id(frame)] = hashlib.sha256(jpg_bytes).hexdigest()\n                if len(_payload_hashes) > 2048:\n                    _payload_hashes.pop(next(iter(_payload_hashes)))\n'+anchor)
    anchor='                current_time = time.time()\n                cache_entry = depth_cache[boat_side]'
    assert vision.count(anchor)==1
    vision=vision.replace(anchor,'                if role == "front":\n                    _audit_log.write(json.dumps({"hash": _payload_hashes.get(id(frame)), "camera": stream_name, "bbox": best_box, "detections": yolo_display_detections}) + "\\n")\n'+anchor)
    (project/'Assets/usv/vision.py').write_text(prefix+vision)


def run(tag,model,scenario,radius,duration):
    project=WORK/'project';output=OUT/(tag+'_'+scenario)
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    instrument_python(project,output,model,radius)
    job=output/'job.json';job.write_text(json.dumps({'output':str(output),'duration':duration}))
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['USV_SELECTION_AUDIT']=str(output/'selected-targets.jsonl')
    log=(output/'controller.log').open('w')
    ctrl=subprocess.Popen([PYTHON,'-u','usv_controller.py'],cwd=project/'Assets',env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        env['__NV_PRIME_RENDER_OFFLOAD']='1';env['__GLX_VENDOR_LIBRARY_NAME']='nvidia'
        player=subprocess.Popen([str(WORK/'build/usv_model_test.x86_64'),'-screen-width','960','-screen-height','540',
                                 '-screen-fullscreen','0','-usvmodeltest',str(job),'-logFile',str(output/'player.log')],
                                cwd=WORK/'build',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        try:code=player.wait(timeout=duration+140)
        except subprocess.TimeoutExpired:
            player.terminate();player.wait(timeout=20);raise
    finally:
        ctrl.send_signal(signal.SIGINT)
        try:ctrl.wait(timeout=20)
        except subprocess.TimeoutExpired:ctrl.terminate();ctrl.wait(timeout=10)
        log.close()
    if code or not (output/'complete').exists():raise RuntimeError(f'Unity run failed: {output}')
    with (project/'experiment_metrics/run_summaries.csv').open() as f:rows=list(csv.DictReader(f))
    run_id=rows[-1]['run_id'];summaries=[row for row in rows if row['run_id']==run_id]
    (output/'formation-summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    for row in summaries:
        print(tag,scenario,row['side'],'stale',row['stale_rate_pct'],'RMS m',row['mean_per_boat_rms_m'],flush=True)
    return {'model':tag,'scenario':scenario,'output':str(output),'metrics':summaries}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-build',action='store_true')
    parser.add_argument('--build-only',action='store_true')
    args=parser.parse_args()
    WORK.mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    if not args.no_build:build()
    if args.build_only:return
    records=[]
    for scenario,radius,duration in [('circle',360,90),('sharp',120,60)]:
        for tag,name in [('old','best_v2.pt'),('adapted','best_realisitc.pt')]:
            print('Starting',tag,scenario,flush=True)
            records.append(run(tag,ROOT/name,scenario,radius,duration))
            (OUT/'runs.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':main()

#!/usr/bin/env python3
"""Reproducible fixed-step Kalman ON/OFF study; no production policy tuning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'Tools/boat_dataset'))
from generate_dataset import clone_project,UNITY_DEFAULT
WORK=Path('/tmp/usv-kalman-study')
DATA=ROOT/'Experiments/KalmanStudy/v2'
PYTHON='/home/stanley/miniconda3/envs/unity_boat/bin/python'

CASES=[
 dict(case='C0_calm_circle',sea=0.55,rain=0,dark=False,fog=0,motion='circle',radius=360,gap=0),
 dict(case='C1_huge_waves',sea=3.0,rain=0,dark=False,fog=0,motion='circle',radius=360,gap=0),
 dict(case='C2_heavy_rain',sea=0.9,rain=1.0,dark=False,fog=0.032,motion='circle',radius=360,gap=0),
 dict(case='C3_dark_storm',sea=1.5,rain=1.0,dark=True,fog=0.02,motion='circle',radius=360,gap=0),
 dict(case='C4_turn_dropout_2s',sea=0.55,rain=0,dark=False,fog=0,motion='circle',radius=180,gap=2.0),
 dict(case='C5_speed_s_dropout',sea=1.0,rain=0.4,dark=False,fog=0.01,motion='variable',radius=360,gap=2.0),
 dict(case='C6_brief_dropout',sea=1.2,rain=0.5,dark=False,fog=0.01,motion='circle',radius=220,gap=0.5),
 dict(case='C7_unseen_turn_8s',sea=0.55,rain=0,dark=False,fog=0,motion='unexpected',radius=360,gap=8.0),
]


def patch_python(project,job):
    config=(ROOT/'Assets/usv/config.py').read_text()
    changes=dict(SHOW_WINDOW=False,YOLO_MODEL_PATH=str(ROOT/'best_realistic.pt'),ENABLE_KALMAN_FILTER=job['arm'].startswith('on'),
                 SIMULATED_BBOX_LOSS_ENABLE=job['gap']>0,SIMULATED_BBOX_LOSS_DURATION_SEC=job['gap'],
                 SIMULATED_BBOX_LOSS_INTERVAL_SEC=100 if job['case'].startswith('C7') else 18,
                 SIMULATED_BBOX_LOSS_START_DELAY_SEC=20,SIMULATED_BBOX_LOSS_SIDES='Both')
    for key,value in changes.items():
        config,count=re.subn(r'^'+key+r'\s*=.*$',key+' = '+repr(value),config,flags=re.M)
        assert count==1,key
    (project/'Assets/usv/config.py').write_text(config)
    for name in ['vision.py','control.py','helpers.py']:
        text=(ROOT/'Assets/usv'/name).read_text()
        text=text.replace('import time\n','from study_clock import clock as time\n')
        if name=='vision.py':
            text='import study_runtime\n'+text
            anchor='        while True:\n            pending_streams = []'
            assert text.count(anchor)==1
            text=text.replace(anchor,'        while True:\n            study_runtime.frames_ready.wait()\n            study_runtime.frames_ready.clear()\n            pending_streams = []')
            text=text.replace('model = YOLO(YOLO_MODEL_PATH)','model = study_runtime.AuditYOLO(YOLO(YOLO_MODEL_PATH))')
            anchor='    yolo_uses_cuda, yolo_half_enabled = configure_yolo_runtime(model)'
            assert text.count(anchor)==1
            text=text.replace(anchor,anchor+'\n    torch.backends.cudnn.benchmark = False\n    torch.backends.cudnn.deterministic = True\n    torch.backends.cuda.matmul.allow_tf32 = False\n    torch.backends.cudnn.allow_tf32 = False')
            text=text.replace('    times_dict = {stream_name: time.time() for stream_name in CAMERA_STREAMS}',
                              '    study_runtime.ready.set()\n    times_dict = {stream_name: time.time() for stream_name in CAMERA_STREAMS}')
            anchor='                    if best_box is not None:\n                        if role == "front" and detection_method'
            assert text.count(anchor)==1
            text=text.replace(anchor,'                    study_runtime.record_selection(stream_name, best_box, best_area, center_offset, sim_loss_forced, det_conf_meas)\n'+anchor)
            anchor='    except Exception as exc:\n        print(f"[Vision] Error: {exc}")'
            assert text.count(anchor)==1
            text=text.replace(anchor,'            study_runtime.batch_done.set()\n'+anchor+'\n        study_runtime.error = repr(exc)\n        study_runtime.batch_done.set()')
            if job['arm']=='off_matched':
                text=text.replace('hold_window = KF_COAST_MAX_SEC if kf_active else TRACK_HOLD_SEC','hold_window = KF_COAST_MAX_SEC if kf_active else 3.0')
            if job['arm']=='on_short':
                text=text.replace('hold_window = KF_COAST_MAX_SEC if kf_active else TRACK_HOLD_SEC','hold_window = TRACK_HOLD_SEC')
        compile(text,name,'exec')
        (project/'Assets/usv'/name).write_text(text)
    (project/'Assets/study_clock.py').write_text('from study_runtime import clock\n')


def build():
    project=clone_project(WORK)
    keyboard=project/'Assets/SimpleMove.cs'
    script=keyboard.read_text()
    assert script.count('Input.GetAxis("Vertical")')==1 and script.count('Input.GetAxis("Horizontal")')==1
    keyboard.write_text(script.replace('Input.GetAxis("Vertical")','0.0f').replace('Input.GetAxis("Horizontal")','0.0f'))
    for name in ['StudyRig.cs','StudyRain.cs']:shutil.copy2(HERE/name,project/'Assets'/name)
    shutil.copy2(HERE/'StudyRain.shader',project/'Assets/Resources/StudyRain.shader')
    binary=WORK/'build/study.x86_64';binary.parent.mkdir(exist_ok=True)
    env=os.environ.copy();env['USV_DATASET_BUILD']=str(binary)
    log=WORK/'build.log'
    result=subprocess.run([str(UNITY_DEFAULT),'-batchmode','-projectPath',str(project),'-buildTarget','Linux64',
                           '-executeMethod','USVDatasetBuild.Build','-logFile',str(log)],env=env,
                          stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    text=log.read_text(errors='replace')
    if result.returncode or 'error CS' in text or 'Shader error' in text or '[DatasetBuild] Succeeded' not in text:
        raise RuntimeError(f'Build failed: {log}')
    print('Study Unity build passed.',flush=True)


def plan():
    jobs=[]
    for case in CASES:
        for seed in [1701,1702,1703]:
            arms=['on','off']
            if case['case'].startswith(('C4','C5','C6')):arms.append('off_matched')
            if case['case'].startswith('C4'):arms.append('on_short')
            random.Random(seed+int(case['case'][1])*91).shuffle(arms)
            for arm in arms:
                name=f'{case["case"]}_{seed}_{arm}'
                jobs.append(dict(case,seed=seed,arm=arm,duration=60,port=47500,output=str(DATA/'runs'/name)))
    return jobs


def run(job):
    output=Path(job['output'])
    if (output/'unity.complete').exists() and (output/'bridge.complete').exists():
        print('Skip complete',output.name,flush=True);return
    if output.exists() and any(output.iterdir()):raise RuntimeError(f'Partial run: preserve and inspect {output}')
    output.mkdir(parents=True);path=output/'job.json';path.write_text(json.dumps(job,indent=2)+'\n')
    patch_python(WORK/'project',job)
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['MPLCONFIGDIR']=str(WORK/'mpl');env['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    log=(output/'python.log').open('w')
    bridge=subprocess.Popen([PYTHON,str(HERE/'bridge.py'),str(path),'--assets',str(WORK/'project/Assets')],env=env,stdout=log,stderr=subprocess.STDOUT)
    player=None
    try:
        deadline=time.monotonic()+150
        while not (output/'bridge.ready').exists():
            if bridge.poll() is not None:raise RuntimeError(f'Bridge failed: {output}/python.log')
            if time.monotonic()>deadline:raise TimeoutError('Bridge initialization timeout')
            time.sleep(0.1)
        env['__NV_PRIME_RENDER_OFFLOAD']='1';env['__GLX_VENDOR_LIBRARY_NAME']='nvidia'
        player=subprocess.Popen([str(WORK/'build/study.x86_64'),'-screen-width','640','-screen-height','360','-screen-fullscreen','0',
                                 '-kalmanstudy',str(path),'-logFile',str(output/'unity.log')],cwd=WORK/'build',env=env,
                                stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+600
        while player.poll() is None:
            if bridge.poll() is not None and bridge.returncode!=0:raise RuntimeError(f'Bridge failed: {output}/python.log')
            if time.monotonic()>deadline:raise TimeoutError(f'Simulator timeout: {output}')
            time.sleep(0.2)
        code=player.returncode;bridge_code=bridge.wait(timeout=20)
        if code or bridge_code or not (output/'unity.complete').exists() or not (output/'bridge.complete').exists():
            raise RuntimeError(f'Run failed: {output}')
        print('COMPLETE',output.name,flush=True)
    finally:
        for process in [player,bridge]:
            if process is not None and process.poll() is None:process.terminate();process.wait(timeout=20)
        log.close()


def hashes():
    files=[ROOT/'best_realistic.pt',ROOT/'Assets/usv/config.py',ROOT/'Assets/usv/vision.py',ROOT/'Assets/usv/control.py',ROOT/'Assets/usv/kalman.py',ROOT/'Assets/usv/helpers.py',ROOT/'Assets/usv/state.py',ROOT/'Documentation/KalmanStudy/PROTOCOL.md']
    files+=[HERE/name for name in ['run_study.py','bridge.py','study_runtime.py','StudyRig.cs','StudyRain.cs','StudyRain.shader']]
    files+=[ROOT/name for name in ['Assets/SimpleMove.cs','Assets/HullWaveResponse.cs','Assets/BoatSternWake.cs','Assets/USVOceanSurface.cs','Assets/USVWakeField.cs',
                                  'Assets/SUIMONO - WATER SYSTEM 2/_DEMO/Suimono2_Buoyancy_Demo.unity',
                                  'Assets/SUIMONO - WATER SYSTEM 2/SHADERS/SuimonoFunctionLibrary.cginc',
                                  'ProjectSettings/TimeManager.asset','ProjectSettings/DynamicsManager.asset']]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-build',action='store_true');parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--pilot',action='store_true')
    args=parser.parse_args();WORK.mkdir(exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
    if not args.no_build:build()
    if args.build_only:return
    if args.pilot:
        for tag,case in [('repeat_a',CASES[0]),('repeat_b',CASES[0]),('storm_preview',CASES[3])]:
            run(dict(case,seed=1701,arm='on',duration=25,port=47500,output=str(DATA/'pilots'/tag)))
    else:
        jobs=plan();frozen=DATA/'manifest.json';manifest=dict(jobs=jobs,source_sha256=hashes(),step_hz=10,
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        if frozen.exists():
            if json.loads(frozen.read_text())!=manifest:raise RuntimeError('Source or plan changed after freeze. Use a new study version.')
        else:frozen.write_text(json.dumps(manifest,indent=2)+'\n')
        for index,job in enumerate(jobs):
            print(f'Run {index+1}/{len(jobs)} {Path(job["output"]).name}',flush=True);run(job)


if __name__=='__main__':main()

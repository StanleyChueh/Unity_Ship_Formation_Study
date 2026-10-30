#!/usr/bin/env python3
"""Capture auto-labelled rain / fog / night episodes for YOLO training (dataset v2).

Clones the project (as generate_dataset.py does), patches ONLY the clone's
USVAutomaticDataset.cs to accept `rain`, `fog` and `dark` job settings, and applies the
identical rain overlay (StudyRain shader) and night/overcast lighting values the Kalman
experiments used. Labels still come from the boat identity mask, rendered by a separate
camera without the rain overlay, so weather never alters a label. Your project files
are not modified. Episodes are split train/val/test by episode (no frame leakage).

  python Tools/boat_dataset/generate_weather_dataset.py            # build + capture
  python Tools/boat_dataset/generate_weather_dataset.py --no-build # reuse the build
"""
import argparse
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import time

import generate_dataset as gd

ROOT = gd.ROOT
STUDY = ROOT/'Tools/kalman_study'
# Weather presets = the experiment conditions (same rain overlay, fog and lighting values).
PRESETS = [
    dict(name='rain015', rain=0.15, fog=0.008, dark=False, sea=0.9),
    dict(name='rain025', rain=0.25, fog=0.008, dark=False, sea=1.2),
    dict(name='rain040', rain=0.40, fog=0.010, dark=False, sea=1.0),
    dict(name='heavyrain', rain=1.00, fog=0.032, dark=False, sea=0.9),
    dict(name='fog', rain=0.0, fog=0.020, dark=False, sea=0.9),
    dict(name='night', rain=0.0, fog=0.008, dark=True, sea=1.2),
    dict(name='nightrain015', rain=0.15, fog=0.008, dark=True, sea=1.2),
    dict(name='nightrain040', rain=0.40, fog=0.010, dark=True, sea=1.0),
    dict(name='darkstorm', rain=1.00, fog=0.020, dark=True, sea=1.5),
]

PATCH_FIELDS = ('        public bool spray=true;\n',
                '        public bool spray=true;\n        public float rain=0f, fog=0f;\n        public bool dark=false;\n')
PATCH_STATE = ('    StreamWriter metadata;\n',
               '    StreamWriter metadata;\n    readonly List<StudyRain> rains=new List<StudyRain>();\n'
               '    Light sun;Material sky;RenderTexture cube;bool weather;\n')
PATCH_CALL = ('daylight.sunAzimuth=job.sun_azimuth;daylight.sunIntensity=job.sun_intensity;daylight.enabled=true;}\n',
              'daylight.sunAzimuth=job.sun_azimuth;daylight.sunIntensity=job.sun_intensity;daylight.enabled=true;}\n'
              '        ApplyWeather(water,daylight);\n')
# The Suimono demo's time-of-day script re-sets the sun every LateUpdate; re-apply the
# weather light immediately before each camera render so the frame uses the weather lighting.
PATCH_RENDER = ('        string stem=job.run_id+"_"+sensor.name+"_"+sample.ToString("D4",Invariant);\n',
                '        if(weather)ApplyLight();\n        string stem=job.run_id+"_"+sensor.name+"_"+sample.ToString("D4",Invariant);\n')
WEATHER_METHODS = '''
    // Weather identical to Tools/kalman_study/StudyRig.cs (rain overlay + overcast/night light + fog).
    void ApplyWeather(SuimonoObject water,USVDaylightPresentation daylight)
    {
        foreach(var s in sensors){var r=s.camera.gameObject.AddComponent<StudyRain>();r.seed=job.seed;r.amount=job.rain;rains.Add(r);}
        weather=job.rain>0 || job.dark || job.fog>0;
        if(!weather)return;
        if(daylight!=null)daylight.enabled=false;
        sun=RenderSettings.sun;
        if(sun==null)foreach(var l in FindObjectsOfType<Light>())if(l.type==LightType.Directional){sun=l;break;}
        sky=new Material(Shader.Find("Skybox/Procedural"));materials.Add(sky);
        sky.SetFloat("_Exposure",job.dark ? 0.06f : 0.55f);sky.SetFloat("_AtmosphereThickness",1.4f);
        sky.SetColor("_SkyTint",new Color(0.45f,0.48f,0.52f));RenderSettings.skybox=sky;
        ApplyLight();
        cube=new RenderTexture(128,128,16,RenderTextureFormat.ARGBHalf){dimension=TextureDimension.Cube,useMipMap=true,autoGenerateMips=false};cube.Create();
        var go=new GameObject("Dataset sky capture");var c=go.AddComponent<Camera>();c.enabled=false;c.cullingMask=0;
        c.clearFlags=CameraClearFlags.Skybox;c.RenderToCubemap(cube);cube.GenerateMips();Destroy(go);
        water.customRefCubemap=cube;water.reflectFallback=2;water.enableDynamicReflections=false;
        Debug.Log("[Dataset] weather rain="+job.rain+" fog="+job.fog+" dark="+job.dark);
    }
    void ApplyLight()
    {
        if(sun!=null){sun.transform.rotation=Quaternion.Euler(job.dark ? 8 : 38,job.sun_azimuth,0);sun.intensity=job.dark ? 0.07f : 0.50f;sun.color=new Color(0.82f,0.88f,1f);}
        RenderSettings.ambientMode=AmbientMode.Trilight;
        RenderSettings.ambientSkyColor=job.dark ? new Color(0.03f,0.04f,0.06f) : new Color(0.28f,0.32f,0.36f);
        RenderSettings.ambientEquatorColor=RenderSettings.ambientSkyColor*0.55f;RenderSettings.ambientGroundColor=RenderSettings.ambientSkyColor*0.2f;
        RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;RenderSettings.fogDensity=job.fog;
        RenderSettings.fogColor=job.dark ? new Color(0.025f,0.035f,0.05f) : new Color(0.34f,0.39f,0.43f);
    }
    void LateUpdate()
    {
        foreach(var r in rains)if(r!=null)r.t=Time.time;
        if(weather)ApplyLight();
    }

    void Place('''


def patch_capture(project):
    path = project/'Assets/DatasetCapture/USVAutomaticDataset.cs'
    text = path.read_text()
    for old, new in [PATCH_FIELDS, PATCH_STATE, PATCH_CALL, PATCH_RENDER, ('\n    void Place(', WEATHER_METHODS)]:
        assert text.count(old) == 1, ('capture anchor changed', old[:60])
        text = text.replace(old, new)
    path.write_text(text)
    shutil.copy2(STUDY/'StudyRain.cs', project/'Assets/StudyRain.cs')
    shutil.copy2(STUDY/'StudyRain.shader', project/'Assets/Resources/StudyRain.shader')


def build(work, unity):
    project = gd.clone_project(work)
    patch_capture(project)
    binary = work/'build/usv_dataset.x86_64'
    binary.parent.mkdir(exist_ok=True)
    env = dict(os.environ, USV_DATASET_BUILD=str(binary))
    log = work/'build.log'
    print('Building weather capture player. Log:', log, flush=True)
    result = subprocess.run([str(unity), '-batchmode', '-projectPath', str(project), '-buildTarget', 'Linux64',
                             '-executeMethod', 'USVDatasetBuild.Build', '-logFile', str(log)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    lines = log.read_text(errors='replace').splitlines()
    errors = [s for s in lines if 'error CS' in s or 'Shader error' in s]
    if result.returncode or errors or not any('[DatasetBuild] Succeeded' in s for s in lines):
        raise RuntimeError(f'Unity build failed: {errors[:5]}; see {log}')
    print('Build passed.', flush=True)
    return binary


def make_jobs(output, samples, per_preset_train=3):
    """Per preset: `per_preset_train` train episodes + 1 val + 1 test (whole episodes per split)."""
    jobs, i = [], 0
    for p_index, preset in enumerate(PRESETS):
        for k, split in enumerate(['train']*per_preset_train+['val', 'test']):
            seed = 731000+i*977
            rng = random.Random(seed)
            family = i % 6
            left, right, spacing = [(22, 22, 13), (40, 17, 12), (16, 38, 12), (12, 15, 9), (30, 26, 18), (55, 65, 18)][family]
            heading = rng.uniform(-180, 180)
            run_id = f'{split}_weather_{preset["name"]}_{k:02d}_seed{seed}'
            jobs.append(dict(run_id=run_id, split=split, seed=seed, output=str(output/'raw'/run_id), samples=samples,
                             width=960 if i % 5 == 4 else 640, height=540 if i % 5 == 4 else 360,
                             jpeg_quality=75 if i % 5 == 4 else 55, interval=1.0, warmup=6.0,
                             speed=[18, 14, 18, 10, 20, 18][family], radius=rng.uniform(150, 420), turn=[0, 1, -1][i % 3],
                             heading=heading, left_back=left+rng.uniform(-2, 2), right_back=right+rng.uniform(-2, 2),
                             spacing=spacing, sea=preset['sea'], wake=[1.15, 0.9, 1.35, 0.8, 1.4, 1.15][family],
                             foam=[2.0, 1.5, 2.3, 1.2, 2.4, 2.0][family], spray=True,
                             sun_elevation=rng.uniform(15, 45), sun_azimuth=heading+rng.uniform(-180, 180),
                             sun_intensity=rng.uniform(0.85, 1.25), camera_yaw=rng.uniform(-10, 10),
                             rain=preset['rain'], fog=preset['fog'], dark=preset['dark'], weather=preset['name']))
            i += 1
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--output', type=Path, default=ROOT/'Datasets/boat_weather_v2_raw')
    ap.add_argument('--work', type=Path, default=Path('/tmp/usv-weather-dataset-work'))
    ap.add_argument('--unity', type=Path, default=gd.UNITY_DEFAULT)
    ap.add_argument('--no-build', action='store_true')
    ap.add_argument('--smoke', action='store_true', help='one short episode per preset into the work folder')
    ap.add_argument('--samples', type=int, default=24)
    ap.add_argument('--parallel', type=int, default=5)
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    binary = a.work/'build/usv_dataset.x86_64' if a.no_build else build(a.work, a.unity)
    out = (a.work/'smoke' if a.smoke else a.output).resolve()
    jobs = make_jobs(out, 3 if a.smoke else a.samples, per_preset_train=1 if a.smoke else 3)
    if a.smoke:
        jobs = [j for j in jobs if j['split'] == 'train']
    out.mkdir(parents=True, exist_ok=True)
    plan = out/'capture-plan.json'
    if plan.exists() and json.loads(plan.read_text()) != jobs:
        raise RuntimeError('Existing capture plan differs; choose a new output folder.')
    plan.write_text(json.dumps(jobs, indent=2)+'\n')
    env = dict(os.environ, __NV_PRIME_RENDER_OFFLOAD='1', __GLX_VENDOR_LIBRARY_NAME='nvidia')
    pending = [j for j in jobs if not (Path(j['output'])/(j['run_id']+'.complete')).exists()]
    running, failed = [], []
    while pending or running:
        while pending and len(running) < a.parallel:
            job = pending.pop(0)
            o = Path(job['output'])
            if o.exists() and any(o.iterdir()):
                keep = out/'_partial_runs'
                keep.mkdir(exist_ok=True)
                shutil.move(str(o), str(keep/f'{o.name}_{int(time.time())}'))   # preserved, not deleted
            o.mkdir(parents=True, exist_ok=True)
            path = a.work/(job['run_id']+'.json')
            path.write_text(json.dumps(job, indent=2)+'\n')
            proc = subprocess.Popen([str(binary), '-screen-width', '640', '-screen-height', '360', '-screen-fullscreen', '0',
                                     '-usvdataset', str(path), '-logFile', str(o/'player.log')], cwd=binary.parent, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            running.append((job, proc, time.monotonic()))
            print('start', job['run_id'], flush=True)
        time.sleep(2)
        for item in list(running):
            job, proc, t0 = item
            if proc.poll() is None and time.monotonic()-t0 < 900:
                continue
            if proc.poll() is None:
                proc.kill()
            running.remove(item)
            o = Path(job['output'])
            log = (o/'player.log').read_text(errors='replace') if (o/'player.log').exists() else ''
            ok = (o/(job['run_id']+'.complete')).exists() and 'Exception:' not in log and 'Shader error' not in log
            print(('done ' if ok else 'FAILED ')+job['run_id'], flush=True)
            if not ok:
                failed.append(job['run_id'])
    print('failed:', failed or 'none', flush=True)


if __name__ == '__main__':
    main()

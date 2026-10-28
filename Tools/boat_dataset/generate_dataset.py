#!/usr/bin/env python3
"""Build an isolated Unity player and capture reproducible, auto-labeled runs.

Uses only the Python standard library. Run --smoke first and inspect the label
previews produced by prepare_dataset.py before capturing the complete dataset.
Never launches training or changes the existing detection dataset/controller.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
UNITY_DEFAULT = Path('/home/stanley/Unity/Hub/Editor/2022.3.62f3/Editor/Unity')


def make_jobs(output, samples=24):
    jobs = []
    # Separate complete episodes, including both directions and difficult light.
    for i in range(26):
        rng = random.Random(628100 + i * 991)
        split = 'train' if i < 18 else ('val' if i < 22 else 'test')
        family = i % 6
        left, right, spacing = [(22, 22, 13), (40, 17, 12), (16, 38, 12),
                                (12, 15, 9), (30, 26, 18), (55, 65, 18)][family]
        heading = rng.uniform(-180, 180)
        run_id = f'{split}_{i:02d}_seed{628100 + i * 991}'
        jobs.append(dict(
            run_id=run_id, split=split, seed=628100 + i * 991,
            output=str(output / 'raw' / run_id), samples=samples,
            width=960 if i % 5 == 4 else 640,
            height=540 if i % 5 == 4 else 360,
            jpeg_quality=75 if i % 5 == 4 else 55,
            interval=1.0, warmup=6.0, speed=[18, 14, 18, 10, 20, 18][family],
            radius=rng.uniform(150, 420), turn=[0, 1, -1][i % 3],
            heading=heading, left_back=left + rng.uniform(-2, 2),
            right_back=right + rng.uniform(-2, 2), spacing=spacing,
            sea=[0.55, 0.3, 0.65, 0.15, 0.9, 0.55][family],
            wake=[1.15, 0.9, 1.35, 0.8, 1.4, 1.15][family],
            foam=[2.0, 1.5, 2.3, 1.2, 2.4, 2.0][family], spray=True,
            sun_elevation=[38, 24, 12, 58, 38, 18][family] + rng.uniform(-3, 3),
            sun_azimuth=heading + [145, 110, -25, 60, 170, -45][family],
            sun_intensity=rng.uniform(0.85, 1.25), camera_yaw=rng.uniform(-10, 10),
        ))
    return jobs


def clone_project(work):
    project = work / 'project'
    project.mkdir(parents=True, exist_ok=True)
    for name in ('Assets', 'Packages', 'ProjectSettings'):
        shutil.copytree(ROOT / name, project / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if not (project / 'Library').exists():
        print('Copying Unity import cache into isolated project...', flush=True)
        shutil.copytree(ROOT / 'Library', project / 'Library',
                        ignore=shutil.ignore_patterns('*.lock', 'Bee', 'Search', 'StateCache'))
    editor = project / 'Assets' / 'Editor'
    editor.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__).with_name('USVDatasetBuild.cs'), editor / 'USVDatasetBuild.cs')
    # An old startup command must not determine capture motion.
    (project / 'leader_startup.json').unlink(missing_ok=True)
    return project


def build(work, unity):
    project = clone_project(work)
    binary = work / 'build' / 'usv_dataset.x86_64'
    binary.parent.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['USV_DATASET_BUILD'] = str(binary)
    log = work / 'build.log'
    print('Building isolated capture player. Log:', log, flush=True)
    result = subprocess.run([str(unity), '-batchmode', '-projectPath', str(project),
                             '-buildTarget', 'Linux64', '-executeMethod',
                             'USVDatasetBuild.Build', '-logFile', str(log)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    lines = log.read_text(errors='replace').splitlines()
    errors = [line for line in lines if 'error CS' in line or 'Shader error' in line]
    if result.returncode or errors or not any('[DatasetBuild] Succeeded' in s for s in lines):
        raise RuntimeError(f'Unity build failed: {errors}; see {log}')
    print('Build passed (zero C# / shader errors).', flush=True)
    sources = {}
    for folder in ('Assets/DatasetCapture', 'Assets/Resources'):
        for p in (ROOT / folder).rglob('*'):
            if p.is_file():
                sources[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (work / 'source-sha256.json').write_text(json.dumps(sources, indent=2) + '\n')
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'Datasets/boat_adaptation_v1')
    parser.add_argument('--work', type=Path, default=Path('/tmp/usv-dataset-work'))
    parser.add_argument('--unity', type=Path, default=UNITY_DEFAULT)
    parser.add_argument('--no-build', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--samples', type=int, default=24)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    binary = args.work / 'build/usv_dataset.x86_64' if args.no_build else build(args.work, args.unity)
    if args.build_only:
        return
    args.output = args.output.resolve()
    jobs = make_jobs(args.output, args.samples)
    if args.smoke:
        jobs = [jobs[0] | dict(run_id='smoke', output=str(args.work / 'smoke'), samples=4)]
    elif (args.output / 'capture-plan.json').exists():
        previous = json.loads((args.output / 'capture-plan.json').read_text())
        if previous != jobs:
            raise RuntimeError('Existing capture plan differs; choose a new output folder.')
        if not args.resume:
            raise RuntimeError('Output exists. Use --resume to skip completed runs or choose a new output folder.')
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / 'capture-plan.json').write_text(json.dumps(jobs, indent=2) + '\n')
    env = os.environ.copy()
    env['__NV_PRIME_RENDER_OFFLOAD'] = '1'
    env['__GLX_VENDOR_LIBRARY_NAME'] = 'nvidia'
    for index, job in enumerate(jobs):
        out = Path(job['output'])
        complete = out / (job['run_id'] + '.complete')
        if args.resume and complete.exists():
            print('Skip completed', job['run_id'], flush=True)
            continue
        if out.exists() and any(out.iterdir()):
            raise RuntimeError(f'Partial run exists at {out}. Preserve it and use a new output directory.')
        out.mkdir(parents=True, exist_ok=True)
        path = args.work / (job['run_id'] + '.json')
        path.write_text(json.dumps(job, indent=2) + '\n')
        print(f'Capture {index + 1}/{len(jobs)}: {job["run_id"]}', flush=True)
        result = subprocess.run([str(binary), '-screen-width', '640', '-screen-height', '360',
                                 '-screen-fullscreen', '0', '-usvdataset', str(path),
                                 '-logFile', str(out / 'player.log')],
                                cwd=binary.parent, env=env, timeout=900,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        log = (out / 'player.log').read_text(errors='replace')
        if result.returncode or not complete.exists() or any(s in log for s in ('Exception:', 'Shader error')):
            raise RuntimeError(f'Capture failed; see {out / "player.log"}')
        print('Saved', complete.read_text(), 'images to', out, flush=True)


if __name__ == '__main__':
    main()

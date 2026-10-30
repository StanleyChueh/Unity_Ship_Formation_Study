#!/usr/bin/env python3
"""Merge the v1 YOLO dataset with the captured rain/fog/night episodes into dataset v2.

Output: Datasets/boat_adaptation_v2_weather_yolo/
  train, val, test            v1 images (unchanged) + weather episodes of that split
  val_weather, test_weather   weather-only copies, for measuring night/rain detection alone
  data.yaml                   combined dataset (classes unchanged: 0 leader, 1 follower)
  data_weather_eval.yaml      evaluate on weather-only val/test
  audit.json, previews/, README.md, and a zip + sha256 next to the folder for Colab.
Low-contrast boxes (boat geometrically visible but nearly invisible in the RGB, e.g. heavy
fog or night) are flagged in audit.json, not removed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
NAMES = {0: 'leader', 1: 'follower'}
LOW_CONTRAST = 0.03   # |mean luminance inside box - surrounding ring| / 255


def labels_of(path):
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            c, x, y, w, h = line.split()
            out.append((int(c), float(x), float(y), float(w), float(h)))
    return out


def contrast(img, box):
    W, H = img.shape[1], img.shape[0]
    c, x, y, w, h = box
    x0, x1 = int((x-w/2)*W), int((x+w/2)*W)
    y0, y1 = int((y-h/2)*H), int((y+h/2)*H)
    pad = 6
    X0, X1, Y0, Y1 = max(0, x0-pad), min(W, x1+pad), max(0, y0-pad), min(H, y1+pad)
    outer = img[Y0:Y1, X0:X1].astype(float)
    inner = img[max(0, y0):min(H, y1), max(0, x0):min(W, x1)].astype(float)
    if inner.size == 0 or outer.size <= inner.size:
        return None
    ring_mean = (outer.sum()-inner.sum())/(outer.size-inner.size)
    return abs(inner.mean()-ring_mean)/255.0


def preview(items, path, title):
    tiles = []
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    for img_path, lab_path in items[:12]:
        im = Image.open(img_path).convert('RGB').resize((480, 270))
        d = ImageDraw.Draw(im)
        for c, x, y, w, h in labels_of(lab_path):
            box = ((x-w/2)*480, (y-h/2)*270, (x+w/2)*480, (y+h/2)*270)
            col = (60, 220, 120) if c == 0 else (255, 150, 40)
            d.rectangle(box, outline=col, width=2)
            d.text((box[0], max(0, box[1]-15)), NAMES[c], fill=col, font=font)
        tiles.append(im)
    if not tiles:
        return
    cols = 4
    rows = (len(tiles)+cols-1)//cols
    sheet = Image.new('RGB', (cols*480, rows*270+34), (20, 22, 26))
    ImageDraw.Draw(sheet).text((8, 8), title+'   (green = leader, orange = follower; labels from identity mask)', fill=(255, 255, 255), font=font)
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols)*480, 34+(k//cols)*270))
    sheet.save(path, quality=90)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--v1', type=Path, default=ROOT/'Datasets/boat_adaptation_v1_yolo')
    ap.add_argument('--raw', type=Path, default=ROOT/'Datasets/boat_weather_v2_raw')
    ap.add_argument('--out', type=Path, default=ROOT/'Datasets/boat_adaptation_v2_weather_yolo')
    ap.add_argument('--no-zip', action='store_true')
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit(f'{a.out} exists; remove or choose another --out (nothing overwritten).')
    plan = json.loads((a.raw/'capture-plan.json').read_text())
    missing = [j['run_id'] for j in plan if not (Path(j['output'])/(j['run_id']+'.complete')).exists()]
    if missing:
        raise SystemExit(f'{len(missing)} capture runs incomplete, e.g. {missing[:3]}')
    for split in ['train', 'val', 'test', 'val_weather', 'test_weather']:
        for sub in ['images', 'labels']:
            (a.out/split/sub).mkdir(parents=True)
    audit = dict(v1={}, weather=defaultdict(lambda: defaultdict(Counter)), low_contrast_examples=[])
    # 1) v1 unchanged
    for split in ['train', 'val', 'test']:
        n = 0
        for img in sorted((a.v1/split/'images').iterdir()):
            lab = a.v1/split/'labels'/(img.stem+'.txt')
            shutil.copy2(img, a.out/split/'images'/img.name)
            if lab.exists():
                shutil.copy2(lab, a.out/split/'labels'/lab.name)
            n += 1
        audit['v1'][split] = n
    # 2) weather episodes (whole episode stays in its split)
    by_preset = defaultdict(list)
    contrasts = defaultdict(list)
    for job in plan:
        run = Path(job['output'])
        for img in sorted((run/'images').glob('*.jpg')):
            lab = run/'labels'/(img.stem+'.txt')
            boxes = labels_of(lab)
            for c, x, y, w, h in boxes:
                assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1, (lab, x, y, w, h)
            for dest in [job['split'], job['split']+'_weather'] if job['split'] != 'train' else ['train']:
                shutil.copy2(img, a.out/dest/'images'/img.name)
                shutil.copy2(lab, a.out/dest/'labels'/lab.name)
            stats = audit['weather'][job['split']][job['weather']]
            stats['images'] += 1
            stats['empty_images'] += int(not boxes)
            gray = np.asarray(Image.open(img).convert('L'))
            for b in boxes:
                stats[NAMES[b[0]]+'_boxes'] += 1
                cval = contrast(gray, b)
                if cval is not None:
                    contrasts[job['weather']].append(cval)
                    if cval < LOW_CONTRAST:
                        stats['low_contrast_boxes'] += 1
                        if len(audit['low_contrast_examples']) < 40:
                            audit['low_contrast_examples'].append(dict(image=img.name, class_name=NAMES[b[0]], contrast=round(cval, 4)))
            if job['split'] == 'train':
                by_preset[job['weather']].append((img, lab))
    audit['weather'] = {s: {w: dict(c) for w, c in d.items()} for s, d in audit['weather'].items()}
    audit['median_box_contrast_by_weather'] = {w: round(float(np.median(v)), 4) for w, v in contrasts.items()}
    audit['low_contrast_threshold'] = LOW_CONTRAST
    audit['totals'] = {split: len(list((a.out/split/'images').iterdir())) for split in ['train', 'val', 'test', 'val_weather', 'test_weather']}
    (a.out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    (a.out/'data.yaml').write_text('train: train/images\nval: val/images\ntest: test/images\nnames:\n  0: leader\n  1: follower\n')
    (a.out/'data_weather_eval.yaml').write_text('train: train/images\nval: val_weather/images\ntest: test_weather/images\nnames:\n  0: leader\n  1: follower\n')
    (a.out/'previews').mkdir()
    for preset, items in by_preset.items():
        step = max(1, len(items)//12)
        preview(items[::step], a.out/'previews'/f'train_{preset}.jpg', f'train / {preset}')
    t = audit['totals']
    rows = '\n'.join(f'| {w} | ' + ' | '.join(str(audit['weather'].get(s, {}).get(w, {}).get('images', 0)) for s in ['train', 'val', 'test'])
                     + f' | {audit["median_box_contrast_by_weather"].get(w, 0):.3f} |' for w in sorted(contrasts))
    (a.out/'README.md').write_text(f'''# boat_adaptation_v2_weather_yolo

Dataset v1 (`boat_adaptation_v1_yolo`, unchanged) **plus** auto-labelled rain / fog / night
episodes captured with `Tools/boat_dataset/generate_weather_dataset.py`. Classes unchanged:
`0 = leader`, `1 = follower`. Labels come from the Unity boat identity mask (rendered without the
rain overlay), exactly as in v1. Episodes are split train/val/test as whole episodes.

| Split | Images |
|---|---:|
| train | {t["train"]} (v1 {audit["v1"]["train"]} + weather) |
| val | {t["val"]} (v1 {audit["v1"]["val"]} + weather) |
| test | {t["test"]} (v1 {audit["v1"]["test"]} + weather) |
| val_weather / test_weather | {t["val_weather"]} / {t["test_weather"]} (weather only) |

Weather episodes (images per split, median box contrast):

| Weather | train | val | test | median contrast |
|---|---:|---:|---:|---:|
{rows}

Weather = the same synthetic rain overlay, fog and night/overcast lighting as the Kalman
experiments (`Tools/kalman_study/StudyRig.cs`). This trains the detector for *these simulated*
conditions; it is not a validated model of real rain or real night cameras.

Labels are geometric: a boat that is unoccluded by geometry is labelled even if heavy fog or
darkness makes it nearly invisible in the image. `audit.json` counts such low-contrast boxes
(contrast < {LOW_CONTRAST}) per weather and lists examples; inspect `previews/` before training.

Train (same settings as v1), fine-tuning your current detector: `python Tools/boat_dataset/train.py --data Datasets/boat_adaptation_v2_weather_yolo/data.yaml --model best_realistic.pt`
(or upload `boat_adaptation_v2_weather_yolo.zip` to Colab). Evaluate weather-only with
`yolo detect val model=<best.pt> data=Datasets/boat_adaptation_v2_weather_yolo/data_weather_eval.yaml split=test imgsz=640`,
and keep checking v1 test (`Datasets/boat_adaptation_v1_yolo/data.yaml`) so clear-weather accuracy does not regress.
''')
    if not a.no_zip:
        z = a.out.with_suffix('.zip')
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_STORED) as zf:
            for p in sorted(a.out.rglob('*')):
                if p.is_file():
                    zf.write(p, Path(a.out.name)/p.relative_to(a.out))
        h = hashlib.sha256(z.read_bytes()).hexdigest()
        z.with_suffix('.zip.sha256').write_text(f'{h}  {z.name}\n')
    print(json.dumps(audit['totals']), flush=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Audit identity labels, mix legacy training images, and make a YOLO dataset.

Requires Pillow and numpy (already present in the unity_boat environment).
Does not train or replace any model. Uses complete-run splits from capture-plan.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import shutil

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
NAMES = {0: 'leader', 1: 'follower'}


def read_labels(path):
    labels = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        assert len(fields) == 5, (path, line)
        cls, x, y, w, h = map(float, fields)
        assert cls in NAMES and all(math.isfinite(v) for v in (x, y, w, h)), (path, line)
        assert 0 < w <= 1 and 0 < h <= 1, (path, line)
        assert x-w/2 >= -1e-5 and y-h/2 >= -1e-5 and x+w/2 <= 1+1e-5 and y+h/2 <= 1+1e-5, (path, line)
        labels.append((int(cls), x, y, w, h))
    return labels


def audit_frame(folder, frame):
    stem = frame['stem']
    labels = read_labels(folder / 'labels' / (stem + '.txt'))
    with Image.open(folder / 'images' / (stem + '.jpg')) as image:
        width, height = image.size
        image.verify()
    assert (width, height) == (frame['width'], frame['height']), stem
    mask = np.asarray(Image.open(folder / 'masks' / (stem + '.png')))[:, :, 0]
    assert mask.shape == (height, width) and set(np.unique(mask)) <= {0, 1, 2, 3}, stem
    expected = []
    for identity in (1, 2, 3):
        ys, xs = np.where(mask == identity)
        if not len(xs):
            continue
        x, y, w, h = int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)
        if len(xs) < 16 or w < 3 or h < 3:
            continue
        expected.append((0 if identity == 1 else 1, (x+w/2)/width, (y+h/2)/height, w/width, h/height))
    assert len(expected) == len(labels) == len(frame['boxes']), stem
    for a, b, box in zip(expected, labels, frame['boxes']):
        assert a[0] == b[0] == box['class_id'], stem
        assert max(abs(x-y) for x, y in zip(a[1:], b[1:])) < 1e-6, stem
        assert box['instance_id'] in (1, 2, 3) and box['visible_pixels'] >= 16, stem
    return labels


def preview(items, destination, title):
    """A contact sheet of real RGB images with exported labels overlaid."""
    rng = random.Random(413)
    positives = [i for i in items if i['labels']]
    negatives = [i for i in items if not i['labels']]
    chosen = rng.sample(positives, min(14, len(positives))) + rng.sample(negatives, min(2, len(negatives)))
    if not chosen:
        return
    columns, tw, th = 4, 480, 300
    sheet = Image.new('RGB', (columns*tw, math.ceil(len(chosen)/columns)*th+32), '#161b22')
    ImageDraw.Draw(sheet).text((8, 9), title, fill='white')
    for index, item in enumerate(chosen):
        image = Image.open(item['image']).convert('RGB')
        w, h = image.size
        draw = ImageDraw.Draw(image)
        for cls, x, y, bw, bh in item['labels']:
            color = '#ff44ff' if cls == 0 else '#55ff55'
            bounds = ((x-bw/2)*w, (y-bh/2)*h, (x+bw/2)*w, (y+bh/2)*h)
            draw.rectangle(bounds, outline=color, width=2)
            draw.text((bounds[0], max(0, bounds[1]-12)), NAMES[cls], fill=color, stroke_width=1, stroke_fill='black')
        image.thumbnail((tw, th-30))
        x, y = index % columns*tw, 32+index//columns*th
        sheet.paste(image, (x, y))
        ImageDraw.Draw(sheet).text((x+4, y+th-24), item['stem'][:65], fill='white')
    sheet.save(destination)


def load_runs(root, smoke=False):
    if smoke:
        job = json.loads((root / 'smoke.job.json').read_text())
        jobs = [job]
    else:
        jobs = json.loads((root / 'capture-plan.json').read_text())
    result = []
    for job in jobs:
        folder = Path(job['output'])
        marker = folder / (job['run_id']+'.complete')
        assert marker.exists(), f'Run not complete: {folder}'
        frames = [json.loads(line) for line in (folder / (job['run_id']+'.jsonl')).read_text().splitlines()]
        assert len(frames) == int(marker.read_text()) == job['samples']*4, job['run_id']
        for frame in frames:
            assert frame['run_id'] == job['run_id'] and frame['split'] == job['split']
            labels = audit_frame(folder, frame)
            result.append(dict(frame, labels=labels, image=folder / 'images' / (frame['stem']+'.jpg'),
                               label=folder / 'labels' / (frame['stem']+'.txt'), source='unity_identity_mask'))
    return result


def background_crops(root, items):
    """Add empty sky/water regions from training episodes only.

    Identity masks must contain no boat pixel anywhere inside the crop, even a
    fragment smaller than the positive-label threshold. Validation/test remain
    complete camera frames. Store crop provenance for repeatable auditing.
    """
    output = root / 'raw/background_crops'
    for name in ('images', 'labels'):
        (output / name).mkdir(parents=True, exist_ok=True)
    added = []
    candidates = [i for i in items if i['split'] == 'train']
    for item in candidates[::6]:
        mask = np.asarray(Image.open(item['image'].parent.parent / 'masks' / (item['stem']+'.png')))[:, :, 0]
        image = Image.open(item['image']).convert('RGB')
        width, height = image.size
        region = None
        for fraction in (0.60, 0.50, 0.40, 0.33):
            cw, ch = round(width*fraction), round(height*fraction)
            # Keep the horizon in most crops and some textured water beneath it.
            top = round(height*(0.50-fraction*0.5))
            for x in np.linspace(0, width-cw, 13).astype(int):
                if mask[top:top+ch, x:x+cw].any():
                    continue
                crop = image.crop((x, top, x+cw, top+ch))
                pixels = np.asarray(crop).astype(float)
                lower = pixels[ch//2:]
                texture = np.abs(np.diff(lower, axis=0)).mean()
                if texture > 0.8:
                    region = (int(x), top, int(x+cw), top+ch)
                    break
            if region:
                break
        if not region:
            continue
        stem = item['stem']+'_empty_water'
        target = output / 'images' / (stem+'.jpg')
        label = output / 'labels' / (stem+'.txt')
        image.crop(region).save(target, quality=item['jpeg_quality'])
        label.write_text('')
        added.append(dict(stem=stem, split='train', run_id=item['run_id'], image=target, label=label,
                          labels=[], width=region[2]-region[0], height=region[3]-region[1],
                          source='unity_background_crop', source_frame=item['stem'], crop_box=region))
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT / 'Datasets/boat_adaptation_v1')
    parser.add_argument('--legacy', type=Path, default=Path('/home/stanley/Github/Unity_boat_detection'))
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    items = load_runs(args.root, args.smoke)
    if args.smoke:
        preview(items, args.root / 'labels-preview.jpg', 'Automatic identity labels: small capture audit')
        print('PASS: identity-mask / YOLO / metadata audit on', len(items), 'images')
        print('Instances', dict(Counter(NAMES[label[0]] for item in items for label in item['labels'])))
        return
    items.extend(background_crops(args.root, items))
    # Whole episodes already have a fixed split. Deduplicate exact image bytes
    # across all splits as a second guard, including the legacy dataset.
    seen = {}
    duplicates = []
    retained = []
    stats = defaultdict(lambda: dict(images=0, negatives=0, instances=Counter(), sources=Counter(), sizes=Counter()))
    for split in ('train', 'val', 'test', 'legacy_val'):
        (args.root / split / 'images').mkdir(parents=True, exist_ok=True)
        (args.root / split / 'labels').mkdir(parents=True, exist_ok=True)
    for source_split, destination_split in [('train', 'train'), ('val', 'legacy_val')]:
        folder = args.legacy / source_split
        for image in sorted((folder / 'images').glob('*')):
            if image.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                continue
            label = folder / 'labels' / (image.stem+'.txt')
            labels = read_labels(label)
            with Image.open(image) as im:
                width, height = im.size
                im.verify()
            items.append(dict(stem='legacy_'+source_split+'_'+image.stem, split=destination_split,
                              run_id='legacy_'+source_split, image=image, label=label, labels=labels,
                              width=width, height=height, source='legacy_manual'))
    # Prioritize new test/val if an identical image happens to be in legacy data.
    priority = {'test': 0, 'val': 1, 'train': 2, 'legacy_val': 3}
    items.sort(key=lambda i: (priority[i['split']], i['stem']))
    for item in items:
        digest = hashlib.sha256(item['image'].read_bytes()).hexdigest()
        if digest in seen:
            duplicates.append(dict(dropped=item['stem'], kept=seen[digest], split=item['split']))
            continue
        seen[digest] = item['stem']
        split = item['split']
        image = args.root / split / 'images' / (item['stem']+item['image'].suffix.lower())
        label = args.root / split / 'labels' / (item['stem']+'.txt')
        if image.exists() and hashlib.sha256(image.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Refusing to overwrite different image: '+str(image))
        shutil.copy2(item['image'], image)
        shutil.copy2(item['label'], label)
        stat = stats[split]
        stat['images'] += 1
        stat['negatives'] += not bool(item['labels'])
        stat['instances'].update(NAMES[l[0]] for l in item['labels'])
        stat['sources'][item['source']] += 1
        stat['sizes'][f'{item["width"]}x{item["height"]}'] += 1
        retained.append(dict(item, image=image, label=label, sha256=digest))
    # Omitting `path` makes Ultralytics resolve paths relative to this YAML file,
    # verified against the installed check_det_dataset implementation.
    (args.root / 'data.yaml').write_text('train: train/images\nval: val/images\ntest: test/images\nnames:\n  0: leader\n  1: follower\n')
    (args.root / 'legacy_val.yaml').write_text('train: train/images\nval: legacy_val/images\nnames:\n  0: leader\n  1: follower\n')
    runs = defaultdict(set)
    for item in retained:
        if item['source'] == 'unity_identity_mask':
            runs[item['split']].add(item['run_id'])
    assert not (runs['train'] & runs['val'] or runs['train'] & runs['test'] or runs['val'] & runs['test'])
    report = dict(splits=stats, new_capture_runs={k: sorted(v) for k, v in runs.items()},
                  exact_duplicates_removed=duplicates, identity_mask_audit='passed',
                  annotation_policy='Visible boat mesh bounds, water/opaque depth occlusion; transparent spray is not a hard occluder; no wake/spray in boat labels; all three boat instances including visible camera owner.',
                  minimum_visible_pixels=16, minimum_box_side_pixels=3,
                  training_background_crops=sum(i['source']=='unity_background_crop' for i in retained),
                  legacy_split_warning='Original legacy train/val frame grouping is unknown. legacy_val is reported separately, not used for new validation or test.')
    (args.root / 'audit.json').write_text(json.dumps(report, indent=2)+'\n')
    with (args.root / 'index.jsonl').open('w') as out:
        for item in retained:
            data = {k: v for k, v in item.items() if k not in ('labels', 'image', 'label')}
            data['image'] = str(item['image'].relative_to(args.root))
            data['label'] = str(item['label'].relative_to(args.root))
            out.write(json.dumps(data)+'\n')
    for split in ('train', 'val', 'test'):
        selected = [item for item in retained if item['split'] == split and item['source'].startswith('unity_')]
        preview(selected, args.root / (split+'-preview.jpg'), split+' — new captures with exported YOLO labels')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

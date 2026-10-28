#!/usr/bin/env python3
"""Prepare minimal YOLO data and a separate model folder; never upload files."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def labels_valid(path):
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f'Invalid YOLO label: {path}')
        cls, x, y, w, h = map(float, fields)
        if not (cls in (0, 1) and all(math.isfinite(v) for v in (x, y, w, h))
                and 0 < w <= 1 and 0 < h <= 1
                and x-w/2 >= -1e-5 and y-h/2 >= -1e-5
                and x+w/2 <= 1+1e-5 and y+h/2 <= 1+1e-5):
            raise ValueError(f'Out-of-range YOLO label: {path}')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'Datasets/boat_adaptation_v1')
    parser.add_argument('--dataset-output', type=Path, default=ROOT/'Datasets/boat_adaptation_v1_yolo')
    parser.add_argument('--model', type=Path, default=ROOT/'best_v2.pt')
    parser.add_argument('--model-output', type=Path, default=ROOT/'Datasets/boat_detector_starting_model')
    args = parser.parse_args()
    for output in (args.dataset_output, args.model_output):
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f'Choose an empty destination; export refuses to mix existing files: {output}')
    archive_path = args.dataset_output.with_name(args.dataset_output.name+'_clean.zip')
    if archive_path.exists():
        raise FileExistsError(f'Archive already exists: {archive_path}')
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    expected = set()
    counts = {}
    for split in ('train', 'val', 'test'):
        images = sorted(p for p in (args.source/split/'images').iterdir()
                        if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png'))
        if not images or len({p.stem for p in images}) != len(images):
            raise ValueError(f'Missing images or duplicate stems: {split}')
        labels = {p.stem for p in (args.source/split/'labels').glob('*.txt')}
        if labels != {p.stem for p in images}:
            raise ValueError(f'Image/label pairing mismatch: {split}')
        for folder in ('images', 'labels'):
            (args.dataset_output/split/folder).mkdir(parents=True, exist_ok=True)
        for image in images:
            label = args.source/split/'labels'/(image.stem+'.txt')
            labels_valid(label)
            for source, relative in [(image, Path(split)/'images'/image.name),
                                     (label, Path(split)/'labels'/label.name)]:
                target = args.dataset_output/relative
                shutil.copy2(source, target)
                if digest(source) != digest(target):
                    raise IOError(f'Copy checksum mismatch: {source}')
                expected.add(relative.as_posix())
        counts[split] = len(images)
    # No absolute machine paths: Ultralytics resolves against the YAML location.
    (args.dataset_output/'data.yaml').write_text(
        'train: train/images\nval: val/images\ntest: test/images\nnames:\n  0: leader\n  1: follower\n')
    expected.add('data.yaml')
    actual = {p.relative_to(args.dataset_output).as_posix() for p in args.dataset_output.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError(f'Unexpected export content: {actual ^ expected}')
    args.model_output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.model, args.model_output/args.model.name)
    model_hash = digest(args.model_output/args.model.name)
    if model_hash != digest(args.model):
        raise IOError('Model checksum mismatch')
    with zipfile.ZipFile(archive_path, 'w', allowZip64=True) as archive:
        for relative in sorted(expected):
            p = args.dataset_output/relative
            archive.write(p, Path(args.dataset_output.name)/relative,
                          compress_type=zipfile.ZIP_STORED if p.suffix.lower() in ('.png', '.jpg', '.jpeg') else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise IOError('ZIP CRC validation failed')
        if set(archive.namelist()) != {args.dataset_output.name+'/'+r for r in expected}:
            raise ValueError('Unexpected ZIP contents')
    report = dict(dataset=str(args.dataset_output), model=str(args.model_output),
                  archive=str(archive_path), images=counts, dataset_files=len(expected),
                  archive_bytes=archive_path.stat().st_size, archive_sha256=digest(archive_path),
                  model_filename=args.model.name, model_sha256=model_hash,
                  copied_files_sha256_verified=True, labels_validated=True,
                  extra_dataset_files=[], uploaded=False)
    report_path = ROOT/'Documentation/AutomaticBoatDataset/huggingface-export-check.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    archive_path.with_suffix('.zip.sha256').write_text(report['archive_sha256']+'  '+archive_path.name+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

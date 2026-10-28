#!/usr/bin/env python3
"""Optional user-run fine-tuning entry point. Dataset generation never runs this."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'Datasets/boat_adaptation_v1/data.yaml')
    parser.add_argument('--model', type=Path, default=ROOT / 'best_v2.pt')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch', type=int, default=16)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--device', default='0')
    args = parser.parse_args()
    if not args.data.is_file() or not args.model.is_file():
        parser.error('Dataset YAML and starting checkpoint must exist.')
    from ultralytics import YOLO
    model = YOLO(str(args.model.resolve()))
    # A fresh fine-tuning run from the old weights, not a resume of its optimizer.
    model.train(data=str(args.data.resolve()), epochs=args.epochs, batch=args.batch,
                imgsz=args.imgsz, device=args.device, optimizer='AdamW', lr0=0.001,
                patience=12, seed=628100, mosaic=0.3, close_mosaic=8,
                hsv_h=0.015, hsv_s=0.35, hsv_v=0.3, scale=0.3,
                translate=0.08, flipud=0.0, fliplr=0.5,
                project=str(ROOT / 'runs/boat_adaptation'), name='finetune',
                exist_ok=False)


if __name__ == '__main__':
    main()

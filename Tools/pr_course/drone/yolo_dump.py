"""Run the teammate's best.pt on every frame (full frame, imgsz 960, low conf 0.05 so every candidate is kept).
Matches his detect(): the roi argument is ignored there, so full-frame detection per frame is exact.
Usage: python yolo_dump.py WEIGHTS VIDEO OUT.json"""
import json, sys, time, cv2
from ultralytics import YOLO
m = YOLO(sys.argv[1]); cap = cv2.VideoCapture(sys.argv[2]); out = []; ts = []
while True:
    ok, fr = cap.read()
    if not ok: break
    H, W = fr.shape[:2]
    t = time.perf_counter()
    r = m.predict(fr, imgsz=960, conf=0.05, iou=0.45, device=0, verbose=False)[0]
    ts.append(time.perf_counter() - t)
    out.append([[*b.xyxy[0].tolist(), float(b.conf[0])] for b in r.boxes])
json.dump(dict(W=W, H=H, frames=out, median_ms=1000 * sorted(ts)[len(ts) // 2]), open(sys.argv[3], "w"))
print(sys.argv[2], len(out), "frames, median", 1000 * sorted(ts)[len(ts) // 2], "ms")

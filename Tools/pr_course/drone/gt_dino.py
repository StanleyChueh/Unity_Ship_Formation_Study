"""Pseudo ground truth for the drone videos, independent of the YOLO model under test.
Grounding DINO base, 2 prompts x horizontal flip = 4 opinions per frame (same recipe as the teammate's
autolabel_v2.py, but WITHOUT the YOLO opinion). Writes every opinion's boxes so fusion can be redone offline.
Usage: python gt_dino.py VIDEO OUT.json"""
import json, sys, cv2, torch
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
BG = ("fan", "chair", "cable", "monitor", "door")
PROMPTS = ("drone. fan. chair. cable. monitor. door.", "a quadcopter. a small white drone.")
MID = "IDEA-Research/grounding-dino-base"
proc = AutoProcessor.from_pretrained(MID)
model = AutoModelForZeroShotObjectDetection.from_pretrained(MID).to("cuda").eval()

def dino(rgb, prompt, W, H):
    inp = proc(images=rgb, text=prompt, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        o = model(**inp)
    r = proc.post_process_grounded_object_detection(o, inp.input_ids, threshold=0.15, text_threshold=0.2,
                                                    target_sizes=[(H, W)])[0]
    labs = r["text_labels"] if "text_labels" in r else r["labels"]
    res = []
    for b, s, l in zip(r["boxes"], r["scores"], labs):
        l = str(l)
        if not l.strip() or any(k in l for k in BG): continue
        if prompt == PROMPTS[0] and "drone" not in l: continue
        x1, y1, x2, y2 = [float(t) for t in b.tolist()]
        if (x2 - x1) * (y2 - y1) > 0.5 * W * H: continue
        res.append([x1, y1, x2, y2, float(s)])
    return res

cap = cv2.VideoCapture(sys.argv[1]); out = []
while True:
    ok, fr = cap.read()
    if not ok: break
    H, W = fr.shape[:2]
    rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB); rgbf = rgb[:, ::-1].copy()
    ops = []
    for p in PROMPTS:
        ops.append(dino(rgb, p, W, H))
        ops.append([[W - b[2], b[1], W - b[0], b[3], b[4]] for b in dino(rgbf, p, W, H)])
    out.append(ops)
    if len(out) % 50 == 0: print(sys.argv[1], len(out), flush=True)
json.dump(dict(W=W, H=H, frames=out), open(sys.argv[2], "w"))
print("done", len(out))

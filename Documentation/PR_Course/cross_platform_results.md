# Teammate's drone tracker on both platforms: results (2026-11-04)

The teammate's tracker (`drone_pkg_v4/code/track.py`) combines YOLOv8s (`best.pt`), Lucas-Kanade optical flow and an 8-state
Kalman filter, with a hand-tuned gate. It was replayed offline, frame by frame and deterministically, on both platforms. Each
change based on the course was learned on training data and scored on data it had not seen.

## Setup

| | Drone | USV |
|---|---|---|
| Data | `testv4.mp4` (594 frames) and `IMG_7888.MOV` (932 frames, downscaled to 1080p) | 32 runs from e07 × 2 follower cameras = 64 sequences, 10 Hz, 720p |
| Ground truth | Grounding DINO base: 2 prompts × flip = 4 opinions, fused with his `autolabel_v2` rule. **YOLO is not one of the opinions.** Checked by eye on contact sheets. 524 and 881 frames accepted. | The simulator's true box for the leader |
| Detector | His `best.pt`, full frame, imgsz 960 | Weather-trained `best_realistic_v2.pt`, leader class only |
| Train / test | Cross-video: train on one video, test on the other | Split by seed: 2 folds |
| Latency | L = 1 frame (his RTX setup: YOLO takes 11 ms, a frame lasts 33 ms); L = 3 (a slower board) | L = 1 control step (100 ms) |

**Tracker versions compared:**
- `yolo_only`: the newest delayed YOLO box.
- `his`: a faithful port of his tracker.
- `+learned_Q`: process noise Q chosen by **maximising the innovation log-likelihood** on the training data (maximum likelihood, Ch. 3-1).
- `+learned_RQ`: also measurement noise R fitted by **maximum likelihood** to the errors against ground truth, separately for x and y.
- `bayes_gate+learned_RQ`: his gate replaced by a **Gaussian minimum-risk Bayes classifier** (Ch. 2) with λ_FA/λ_miss = 3. Its
  features are confidence, Mahalanobis distance under the filter's covariance, log area ratio and log aspect ratio.

**Measure:** % of frames with IoU ≥ 0.5 against ground truth. "Fast" means the 20 % of frames where the target's box moves
vertically the most.

## Results, IoU ≥ 0.5 (%), all frames / fast frames

**Drone, L = 1** (his real setup):

| Test video | YOLO only | His | + learned Q | + learned R, Q | + Bayes gate |
|---|---:|---:|---:|---:|---:|
| testv4 | 77.9 / 68.0 | 83.8 / 79.6 | 86.6 / 86.4 | **89.1** / 93.2 | **89.1 / 96.1** |
| IMG_7888 | 81.3 / 63.4 | 79.2 / 77.7 | 82.2 / 84.6 | 82.4 / **86.3** | **88.2** / 82.3 |

On IMG_7888 the Bayes gate cut wrong-target frames from 16.0 % (his tracker) to 7.2 %. On testv4 it had none.

**Drone, L = 3** (slow detector):

| Test video | YOLO only | His | + learned Q | + learned R, Q | + Bayes gate |
|---|---:|---:|---:|---:|---:|
| testv4 | 40.6 / 4.9 | 46.8 / 24.3 | **71.9 / 53.4** | 47.3 / 35.0 | 48.1 / 41.7 |
| IMG_7888 | 52.3 / 1.1 | 56.5 / 26.9 | **81.6 / 70.3** | 57.4 / 34.3 | 58.9 / 34.3 |

**USV, L = 1:**

| Condition | YOLO only | His | + learned Q | + learned R, Q | + Bayes gate |
|---|---:|---:|---:|---:|---:|
| Clear | 85.3 / 65.4 | 73.2 / 53.2 | **88.4 / 81.2** | 88.2 / 80.9 | 70.4 / 68.0 |
| Rain | 89.3 / 73.2 | 80.1 / 62.2 | **91.3 / 83.0** | 89.1 / 79.9 | 81.2 / 75.0 |
| Night | 76.1 / 38.9 | 60.7 / 28.1 | **77.8 / 54.1** | 75.1 / 53.8 | 68.0 / 50.7 |
| Night + rain | 77.1 / 44.9 | 63.1 / 32.5 | **81.1 / 63.3** | 77.8 / 60.9 | 70.8 / 58.4 |
| Dark storm | **73.2** / 41.6 | 53.7 / 26.6 | 58.5 / 38.8 | 53.7 / 38.1 | 44.7 / 33.4 |
| Huge waves | 50.6 / 9.5 | 38.2 / 7.8 | **51.1 / 22.6** | 46.7 / 19.0 | 36.9 / 21.1 |

## Findings

1. **His hand-tuned tracker does not carry over to the boat as it is.** On the USV it is *worse* than raw YOLO in every condition,
   for example 73 % vs 85 % in clear water.
2. **Learning Q by maximum likelihood is the one change that helps on both platforms.** On the USV, maximum likelihood picks
   10× his Q in both folds. That matches the frame rates: at 10 Hz the box moves about 3× as far per step as at 30 fps, so the
   variance is about 9× larger. With learned Q his tracker beats YOLO on the boat in 5 of 6 conditions. In fast frames in
   huge waves it reaches 22.6 % against YOLO's 9.5 %. On the drone with a slow detector, IoU ≥ 0.5 rises from 47–57 % to 72–82 %.
   On the drone the likelihood was still rising at the largest Q tried (100), so the search range should be widened.
3. **A learned R helps only in some cases.** It helps on the drone at L = 1 and hurts at L = 3 and on the boat. The R fit
   compares each YOLO box with ground truth at the frame the image was taken, but the filter uses that box L frames later, so the
   latency error is missing from the noise model. A latency-aware R fit is a clear next task.
4. **The Bayes gate depends on the platform.** On the drone, where real distractors exist (L = 1), it raises accuracy in fast
   frames to 96 % on testv4 and cuts wrong locks on IMG_7888. On the boat, wrong leader-class boxes are rare in these runs
   (2.2 % of candidates). Rejecting true boxes there makes the tracker drift, so the gate makes results worse. The fix to test
   next is a loss sweep (λ, Ch. 2), plus re-acquiring the target after a run of rejections.
5. **The learned versions shake more:** jitter rises (USV clear 1.55 → 1.93 px; drone testv4 9.2 → 20–25 px) because the
   filter follows the target more closely. This is the usual trade-off between lag and smoothness.
6. **Vertical speed against YOLO errors.** On the USV (259 k frames), missed detections rise from 1.8 % to 14.7 % as vertical
   speed goes from 0–2 to 20–40 px per step. On the drone there is no clear trend (misses 7–13 % in every speed bin). Its
   misses are tied to the background (plants, the white tiled wall in the last third of IMG_7888) more than to motion. The
   per-frame speed is also noisy because the pseudo ground-truth boxes jitter; smoothing and normalising by size is still to do.

## Caveats

- There are only two drone videos, so the drone results come from two cross-video folds and are not significance-tested.
- Drone ground truth comes from Grounding DINO, not hand labels. Frames where Grounding DINO is unsure (11.8 % and 5.5 %) are
  not scored.
- USV results are simulation only, and the replay is offline: no closed-loop formation runs were done.
- Learned Q was chosen from a grid (×0.3 to ×300).

## Reproduce

```bash
cd Tools/pr_course
python drone/yolo_dump.py EXP/best.pt EXP/videos/testv4.mp4 EXP/yolo_testv4.json    # same for img7888
python drone/gt_dino.py EXP/videos/testv4.mp4 EXP/gt_dino_testv4.json                # ~25 min per video on an RTX 5050
python drone/analyze.py EXP                                                         # drone tables  (~20 min)
python usv_replay.py ../../Experiments/PR_Course/usv/usv_report.json               # USV tables    (~30 min)
python drone/audit_gt.py EXP testv4 EXP/audit_testv4.jpg 36                         # contact sheet to check GT by eye
```

`EXP` = `Experiments/PR_Course/drone`. That folder (videos, weights, labels, logs) is ignored by git.

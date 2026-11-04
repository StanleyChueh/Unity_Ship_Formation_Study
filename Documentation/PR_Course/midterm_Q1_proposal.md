# Midterm Q1: Final Project Proposal (group project: drone and USV platforms)

**Title:** *Bayesian checking of detections and learned noise models for tracking with YOLO, optical flow and a Kalman filter
under fast vertical image motion: a drone and an unmanned surface vessel (USV)*

---

## 1. Topic

**Shared problem.** Our group tracks one target with a camera on two platforms using the same pipeline: **YOLOv8, then
Lucas-Kanade optical flow, then a Kalman filter**.

- **Drone (teammate):** when the drone climbs or drops quickly, the YOLO box jitters or disappears. Running optical flow every
  frame and fusing it in a Kalman filter keeps a stable box between YOLO results.
- **USV fleet (me):** two follower boats keep formation behind a leader boat using only a forward camera. In huge waves the
  *camera itself* heaves and pitches, so the leader's box moves up and down quickly, the same effect as the drone seen from the
  other side. In my logs, the median vertical speed of the leader's box doubles in huge waves (6 vs 3 px per 0.1 s; 95th
  percentile 21 vs 9.5).

**Evidence that fast vertical motion breaks detection** (USV logs; 259 k frames; current weather-trained detector; scored against
the simulator's true boxes):

| Vertical box speed (px per 0.1 s) | 0–2 | 2–5 | 5–10 | 10–20 | 20–40 |
|---|---:|---:|---:|---:|---:|
| Leader missed | 1.8 % | 2.0 % | 2.5 % | 4.7 % | 14.7 % |
| Wrong box labelled "leader" | 0.5 % | 0.6 % | 0.8 % | 1.9 % | 7.6 % |

**Gap.** The drone tracker works, but its key decisions are hand-tuned:

- a distance and size gate (`GATE = 1.5`, size ratio from 0.25 to 5)
- a ranking score, confidence × e^(−d / gate)
- measurement noise R = 60 · (0.5 / confidence)², the same for x and y
- optical-flow noise R = 30 · (1 + 10 / n), where n is the number of tracked feature points
- a fixed process noise, raised by hand "so the filter keeps up when the drone accelerates"

Pattern recognition gives principled replacements for each one:

| Hand-tuned part | Replacement from the course |
|---|---|
| Gate and ranking score | **Minimum-risk Bayes classifier** (Ch. 2). Classes: ω₁ = target, ω₂ = other boat or object, ω₃ = clutter (wave, spray, rain, background). Gaussian class-conditional densities p(**x**\|ωᵢ) estimated by **MLE** (Ch. 3-1). |
| Hand-set R | **MLE of measurement noise** as a function of confidence, axis (x or y) and motion level (Ch. 3-1) |
| Hand-raised process noise Q | **Recognising the motion regime** (calm or fast vertical) from a short window of track features: Fisher LDA followed by the Bayes rule (Ch. 3-2, Ch. 2) |
| Choice of features | **PCA and Fisher LDA** projections, plus an experimental **Hughes-effect** curve (Ch. 1) |

Minimum-risk acceptance rule. Accepting a wrong box (λ_FA) costs more than rejecting a true one (λ_miss), because the filter can
coast on optical flow and prediction:

  accept the box if Λ(**x**) = p(**x**|ω₁) / p(**x**|ω̄₁) > [(λ_FA − λ_TN) / (λ_miss − λ_TP)] · P(ω̄₁) / P(ω₁)

Features **x** for each candidate box: YOLO confidence, box centre, log width, log height, aspect ratio, number of candidates,
jump from the predicted position, log change in area, **distance between the YOLO box and the box moved by optical flow**, and
the number of good flow points.

**Preliminary results (USV, from existing logs, train and test split by simulation seed):**

1. **Bayes checking of detections.** In huge waves, 6.5 % of boxes YOLO labels "leader" are wrong. A Gaussian Bayes rule raises
   the ROC AUC from 0.85 (confidence alone) to 0.91 and cuts falsely accepted boxes from 718 to 399 (−44 %). It rejects about
   3 % of true leader boxes, the same rate as a confidence threshold of 0.5.
2. **MLE of R contradicts the drone's rule.** As confidence rises from 0.3 to 0.85, the variance of the horizontal error falls
   by about 20×, which the (0.5/s)² rule roughly predicts. The vertical variance barely changes (×0.7 to ×1.0), and the
   vertical error has a bias of about +0.09 box heights. **One noise value scaled by confidence, as in the drone code, is the
   wrong model for vertical motion.**
3. Optical flow alone does not fix the USV (an earlier offline test). It held the leader through only 6 of 12 dropouts in huge
   waves, because the boat is only about 40 px wide and the camera runs at 10 Hz. So on the USV, optical flow is more useful as
   a *feature* for the classifier than as a measurement fed straight into the filter.
4. **The teammate's tracker, tested on both platforms** (offline replay scored against ground truth; details in
   `cross_platform_results.md`). On the boat, his hand-tuned tracker is *worse* than raw YOLO (IoU ≥ 0.5: 73 % vs 85 % in
   clear water). **Choosing the process noise Q by maximum likelihood** picks 10× his value, as expected for 10 Hz against
   30 fps. With it the tracker reaches 88 % in clear water, and in the fastest huge-wave frames it rises from 7.8 % to 22.6 %
   (YOLO alone: 9.5 %). On his drone videos the same learned Q lifts IoU ≥ 0.5 from 47–57 % to 72–82 % when the detector is
   slow (3 frames late). With his real latency (1 frame late), the Bayes gate reaches 96 % on testv4's fastest frames and cuts
   wrong-target frames on IMG_7888 from 16 % to 7 %.

**Division of work.** The drone teammate covers the drone platform, the USV student (me) covers the USV platform, and the
`pr_tracking` module (Bayes checker, MLE noise estimator, regime classifier) is shared. Both platforms are evaluated with the same
protocol.

## 2. Related papers

1. R. O. Duda, P. E. Hart and D. G. Stork, *Pattern Classification*, 2nd ed., Wiley, 2001. Bayes decision theory, MLE, PCA
   and LDA (course textbook).
2. G. F. Hughes, "On the mean accuracy of statistical pattern recognizers," *IEEE Trans. Inf. Theory*, IT-14, 1968. Accuracy
   peaks and then falls as dimension grows.
3. R. A. Fisher, "The use of multiple measurements in taxonomic problems," *Annals of Eugenics*, 1936. Fisher's linear
   discriminant.
4. R. E. Kalman, "A new approach to linear filtering and prediction problems," *J. Basic Eng.*, 1960. The Kalman filter as
   recursive Bayesian estimation.
5. B. D. Lucas and T. Kanade, "An iterative image registration technique with an application to stereo vision," IJCAI 1981; and
   J.-Y. Bouguet, "Pyramidal implementation of the Lucas Kanade feature tracker," Intel tech. report, 2000. The optical flow
   used on both platforms.
6. Z. Kalal, K. Mikolajczyk and J. Matas, "Forward-backward error: automatic detection of tracking failures," ICPR 2010. The
   forward-backward check in our flow step.
7. Y. Bar-Shalom and E. Tse, "Tracking in a cluttered environment with probabilistic data association," *Automatica*, 1975;
   and Y. Bar-Shalom and T. E. Fortmann, *Tracking and Data Association*, Academic Press, 1988. Validation gates in clutter.
8. R. K. Mehra, "On the identification of variances and adaptive Kalman filtering," *IEEE Trans. Autom. Control*, 1970.
   Estimating Q and R from data.
9. H. A. P. Blom and Y. Bar-Shalom, "The interacting multiple model algorithm for systems with Markovian switching
   coefficients," *IEEE Trans. Autom. Control*, 1988. Switching between motion models, our "calm or fast" regime.
10. A. Bewley et al., "SORT," ICIP 2016; and N. Wojke et al., "DeepSORT," ICIP 2017. Combining a detector with a Kalman
    filter and an association step.
11. C. Guo et al., "On calibration of modern neural networks," ICML 2017. A CNN's confidence score is not a calibrated
    posterior.

## 3. Project tasks

**Data.** Data for the USV already exists. I have 652 logged simulator runs (1.05 M front-camera frames; every image is saved).
Each frame logs every raw YOLO box and the true box for each boat, so labels and noise are measured exactly. Weather: clear,
rain, night, night with rain or storm, and huge waves.

The drone has no ground truth. Labels for its test video `testv4.mp4` come from the teammate's own pipeline (Grounding DINO
auto-labels, then manual curation), on every third frame.

| Task | USV (me) | Drone (teammate) | Course link |
|---|---|---|---|
| T1 Dataset | Extract features and labels from 652 runs; split by seed *(pilot done)* | Label `testv4.mp4` | Ch. 1 |
| T2 Error against motion | Miss and false-box rates against vertical box speed *(pilot done)* | The same against the drone's vertical speed | Ch. 1 |
| T3 MLE of noise | Fit R(confidence, axis, motion); check normality; compare with the hand rule *(pilot done)* | The same, for YOLO and flow | Ch. 3-1 |
| T4 Bayes checker | Compare 0-1 loss, minimum risk (sweep λ_FA/λ_miss from 1 to 20) and priors per condition with the hand-tuned gate and confidence thresholds; ROC curves | The same | Ch. 2 |
| T5 Motion regime | LDA and Bayes on a 1 s window (spread of vertical position, flow, innovation) to choose Q | The same | Ch. 2, Ch. 3-2 |
| T6 PCA, LDA, Hughes | 3-class 2-D LDA plot; PCA explained variance; accuracy against d for n = 20 to 10 k | | Ch. 3-2, Ch. 1 |
| T7 Offline tracking replay | Port the drone tracker to saved USV frames. Compare five versions: (a) YOLO only, (b) current USV tracker, (c) drone tracker with hand-tuned settings, (d) (c) with the Bayes checker, (e) (d) with learned R and Q. Measures: error against the true box, IoU, % of frames on the correct target, identity switches, lost tracks | The same five versions on `testv4.mp4` | Whole design cycle |
| T8 Closed loop (optional) | Rerun the huge-wave laps in the existing harness, 3 seeds: formation RMSE and lost-leader events | Live Tello test, if time | Applying the method |

**Schedule** (final date to be confirmed; adjust the last two weeks to fit):

| Week | Dates | Work |
|---|---|---|
| W1 | Nov 5 – Nov 11 | Proposal; 3-minute slides (Nov 11). USV pilots T1–T4 done. |
| W2 | Nov 12 – Nov 18 | Agree the shared feature list and evaluation protocol; drone labels; finish the USV dataset |
| W3 | Nov 19 – Nov 25 | T3 MLE of noise and T4 Bayes checker on both platforms |
| W4 | Nov 26 – Dec 2 | T5 motion regime; T6 PCA, LDA and Hughes curve |
| W5 | Dec 3 – Dec 9 | T7 offline tracking replay on both platforms |
| W6 | Dec 10 – Dec 16 | T8 optional closed loop; compare the two platforms |
| W7 | Dec 17 – Dec 23 | Report, figures, side-by-side videos |
| W8 | Dec 24 → final | Rehearse; spare time for problems |

## 4. Final product

1. **`pr_tracking` Python module, shared by both platforms:** `BayesGate` (MLE training and minimum-risk acceptance),
   `NoiseModel` (R and Q learned by MLE), `RegimeClassifier` (LDA and Bayes). It plugs into the drone `track.py` and the USV
   tracker in place of the hand-tuned constants.
2. **Two labelled datasets:** USV, about 1.6 M candidate boxes with exact ground truth across six weather conditions; drone, a
   labelled test video.
3. **Results package:** tables and figures for T2 to T7 on both platforms.
4. **Side-by-side videos** (YOLO only against the full tracker), like the teammate's current `yolo_vs_combined.mp4`, for the drone
   and for a huge-wave USV lap.

## 5. Project report: components and items

1. Abstract
2. Introduction: tracking from a camera under fast vertical image motion, with a moving target (drone) and a moving camera (USV)
3. Related work: Bayes decisions, detector, optical flow and Kalman tracking, gating and data association, adaptive and
   multiple-model filters, detector calibration
4. Problem formulation: classes ω₁ to ω₃, feature vector **x**, loss matrix λᵢⱼ, the minimum-risk rule derived as a likelihood
   ratio inequality, and the regime classes
5. Method: the shared pipeline; Gaussian MLE (μ̂ and Σ̂, derived); learned R and Q; LDA and PCA
6. Data: USV simulator with exact ground truth; drone video with curated pseudo ground truth; split by seed or by video
7. Results T2 to T7, platform by platform, then compared: what transfers between platforms and what does not (for example,
   optical flow on a large textured drone against a 40 px boat)
8. Discussion: where the Gaussian assumption fails; confidence against posterior; dimension against sample size; limitations
   (USV is simulation only; drone ground truth is approximate; few drone videos)
9. Conclusion and future work: real USV footage, non-parametric densities (Parzen windows, k-nearest neighbours), online
   adaptation
10. References; appendix with code and reproduction steps

## 6. Project presentation (about 15 minutes, both members)

1. Motivation, 2 minutes: drone video (YOLO jitters while climbing or dropping), then USV video (huge waves, leader lost).
   Same problem.
2. Shared pipeline and what is hand-tuned, 2 minutes.
3. Pattern recognition formulation, 3 minutes: classes, features, loss matrix, Bayes rule, MLE, LDA, linked to the lecture
   slides.
4. Results, USV (me), 3 minutes: errors against vertical speed, MLE of R, ROC, replay table.
5. Results, drone (teammate), 3 minutes: the same figures, side-by-side video.
6. Comparing the platforms, conclusion, questions, 2 minutes.

---
*USV pilot reproduction (data in `Experiments/KalmanStudy/robust_evaluation`; scripts in `Tools/pr_course/`):*
`pilot_clf.py` + `pilot_eval.py` (Bayes checker), `motion_pilot.py` (errors against vertical speed), `r_pilot.py` (MLE of R by
confidence). Pilot numbers come from one split by seed and are preliminary.

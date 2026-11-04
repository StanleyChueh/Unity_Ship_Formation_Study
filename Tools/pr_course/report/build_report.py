"""Build the PR course report (HTML -> PDF with headless Chrome). Tables are filled from the experiment JSON files.
Usage: python build_report.py BUILD_DIR OUT.pdf   (run make_figures.py BUILD_DIR/fig first)"""
import json, subprocess, sys, os

ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study"
B, PDF = sys.argv[1], sys.argv[2]
U = json.load(open(f"{ROOT}/Experiments/PR_Course/usv/usv_report.json"))
D = json.load(open(f"{ROOT}/Experiments/PR_Course/drone/drone_report.json"))["results"]
EV = json.load(open(f"{ROOT}/Experiments/PR_Course/rollouts/evidence.json"))
_names = {"all": "All conditions", "clear": "Clear", "rain": "Rain", "night": "Night", "night_rain": "Night + rain", "dark_storm": "Dark storm", "huge_waves": "Huge waves"}
usv_stats = "".join(f"<tr><th class='rowh'>{_names[g]}</th><td>{r['n']}</td><td>{r['better_than_hand']}/{r['n']}</td><td>{r['median_gain_vs_hand']:+.1f}</td><td>{r['p_vs_hand']:.1g}</td>"
                    f"<td>{r['better_than_yolo']}/{r['n']}</td><td>{r['median_gain_vs_yolo']:+.1f}</td><td>{r['p_vs_yolo']:.2g}</td></tr>"
                    for g, r in EV["usv"].items() if g in _names)
_dn = {"L1|testv4": "testv4, 1-frame delay", "L1|img7888": "IMG_7888, 1-frame delay", "L3|testv4": "testv4, 3-frame delay", "L3|img7888": "IMG_7888, 3-frame delay"}
def _ci(r): return f"{r['diff']:+.1f} [{r['ci'][0]:+.1f}, {r['ci'][1]:+.1f}]"
drone_stats = "".join(f"<tr><th class='rowh'>{_dn[k]}</th><td>{_ci(r['learnedQ_minus_his'])}</td><td>{r['learnedQ_minus_his']['blocks_better']} / {r['learnedQ_minus_his']['blocks_worse']} of {r['learnedQ_minus_his']['blocks']}</td>"
                      f"<td>{_ci(r['learnedQ_minus_yolo_only'])}</td></tr>" for k, r in EV["drone"].items())
vid_rows = "".join(f"<tr><td><code>{v['file']}</code></td><td>{v['yolo_only']:.1f}</td><td>{v['his']:.1f}</td><td>{v['learned_Q']:.1f}</td></tr>" for v in EV["usv"]["videos"])
ARMS = [("yolo_only", "YOLO only"), ("his", "Drone tracker, hand-tuned"), ("his+learned_Q", "+ MLE-learned Q"),
        ("his+learned_RQ", "+ MLE-learned R and Q"), ("bayes_gate+learned_RQ", "+ Bayes gate, learned R and Q")]


def svg(name):
    s = open(f"{B}/fig/{name}.svg").read()
    return s[s.index("<svg"):]


def table(rows, get, row_label):
    head = "".join(f"<th>{n}</th>" for _, n in ARMS)
    body = ""
    for key, label in rows:
        vals = [get(key, a) for a, _ in ARMS]
        best_all = max(v[0] for v in vals); best_fast = max(v[1] for v in vals)
        cells = "".join(
            f"<td>{'<b>' if v[0] == best_all else ''}{v[0]:.1f}{'</b>' if v[0] == best_all else ''}"
            f" <span class='fast'>/ {'<b>' if v[1] == best_fast else ''}{v[1]:.1f}{'</b>' if v[1] == best_fast else ''}</span></td>"
            for v in vals)
        body += f"<tr><th class='rowh'>{label}</th>{cells}</tr>"
    return f"<table class='res'><tr><th>{row_label}</th>{head}</tr>{body}</table>"


usv_rows = [("clear", "Clear"), ("rain", "Rain"), ("night", "Night"), ("night_rain", "Night + rain"),
            ("dark_storm", "Dark storm"), ("huge_waves", "Huge waves")]
usv_tab = table(usv_rows, lambda g, a: (U[f"{g}|{a}"]["all"]["success50"], U[f"{g}|{a}"]["fast"]["success50"]), "Condition")
drone_rows = [("L1|testv4", "testv4, 1-frame delay"), ("L1|img7888", "IMG_7888, 1-frame delay"),
              ("L3|testv4", "testv4, 3-frame delay"), ("L3|img7888", "IMG_7888, 3-frame delay")]
drone_tab = table(drone_rows, lambda c, a: (D[f"{c}|{a}"]["all"]["success50"], D[f"{c}|{a}"]["fast"]["success50"]), "Test video")
wl = lambda c, a: D[f"{c}|{a}"]["all"]["wrong_lock"]

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>PR Final Project: Proposal and Method</title>
<style>
@page {{ size: A4; margin: 17mm 17mm 18mm 17mm; @bottom-center {{ content: counter(page); font-size: 8pt; color: #52514e; }} }}
body {{ font-family: 'Liberation Sans', 'Noto Sans CJK TC', sans-serif; font-size: 9.6pt; line-height: 1.42; color: #1a1a19; }}
h1 {{ font-size: 18pt; line-height: 1.2; margin: 0 0 4pt; color: #0b0b0b; }}
.sub {{ color: #52514e; font-size: 10pt; margin-bottom: 10pt; }}
h2 {{ font-size: 13.5pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5px solid #2a78d6; color: #0b0b0b; break-after: avoid; }}
h2.part {{ break-before: page; }}
h3 {{ font-size: 11pt; margin: 12pt 0 4pt; color: #0b0b0b; break-after: avoid; }}
p {{ margin: 0 0 6pt; }} ul, ol {{ margin: 0 0 6pt; padding-left: 16pt; }} li {{ margin-bottom: 2pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; font-size: 8.6pt; break-inside: avoid; }}
th, td {{ border-bottom: 0.6px solid #d6d5d0; padding: 3pt 5pt; text-align: left; vertical-align: top; }}
th {{ background: #f3f2ef; font-weight: bold; }}
table.res td {{ text-align: right; white-space: nowrap; }} table.res th {{ text-align: center; }} th.rowh {{ text-align: left !important; background: none; font-weight: normal; }}
.fast {{ color: #52514e; }}
.box {{ background: #f3f6fb; border-left: 3px solid #2a78d6; padding: 6pt 9pt; margin: 6pt 0 9pt; break-inside: avoid; }}
.warn {{ background: #fbf4ef; border-left: 3px solid #eb6834; padding: 6pt 9pt; margin: 6pt 0 9pt; break-inside: avoid; }}
.eq {{ font-family: 'Liberation Serif', serif; font-size: 11pt; text-align: center; margin: 5pt 0 7pt; }}
.fig {{ text-align: center; margin: 6pt 0 2pt; break-inside: avoid; }} .fig svg {{ max-width: 100%; height: auto; }}
.cap {{ font-size: 8.4pt; color: #52514e; margin: 0 0 10pt; break-before: avoid; }}
.pipe {{ display: flex; align-items: stretch; justify-content: space-between; margin: 8pt 0 4pt; gap: 3pt; break-inside: avoid; }}
.pipe div.n {{ border: 1px solid #b9b8b2; border-radius: 4pt; padding: 5pt 4pt; text-align: center; font-size: 8.4pt; flex: 1; background: #fff; }}
.pipe div.n.pr {{ border: 1.6px solid #2a78d6; background: #f3f6fb; }}
.pipe div.a {{ align-self: center; color: #52514e; font-size: 12pt; }}
.tag {{ display: inline-block; font-size: 7.4pt; color: #fff; background: #2a78d6; border-radius: 3pt; padding: 0 4pt; margin-top: 2pt; }}
.small {{ font-size: 8.6pt; color: #52514e; }}
.cols {{ display: flex; gap: 12pt; }} .cols > div {{ flex: 1; }}
</style></head><body>

<h1>Learning the Tracker from Data: Bayesian Decision and Maximum-Likelihood Methods for Camera-Based Target Tracking on a Drone and an Unmanned Surface Vessel</h1>
<div class="sub">Pattern Recognition, Department of Electrical Engineering, National Taipei University of Technology<br>
Final project: midterm proposal (Question 1) and proposed method for the final presentation<br>
Group members: ______________ (USV platform) &nbsp;·&nbsp; ______________ (drone platform) &nbsp;·&nbsp; 4 November 2026</div>

<div class="box"><b>Summary.</b> Both members of our group track one target with a camera, using the same pipeline:
YOLOv8 finds the target, Lucas-Kanade optical flow moves the box between detections, and a Kalman filter combines them. One
platform is a drone; the other is a fleet of unmanned surface vessels (USVs) that keep formation by following a leader boat.
Both break down when the target's box moves up and down quickly in the image. On the drone the target climbs and drops; on
the USV the camera itself pitches in waves. The current tracker depends on hand-tuned constants. We replace them with course
methods: <b>maximum-likelihood estimation</b> (Ch.&nbsp;3-1) of the filter's noise, a <b>minimum-risk Bayes rule</b> (Ch.&nbsp;2)
for accepting or rejecting each detection, and <b>PCA, Fisher LDA and the Hughes effect</b> (Ch.&nbsp;3-2, Ch.&nbsp;1) for
choosing features. A first offline test already shows the main effect. Choosing the process noise by maximum likelihood turns
the drone tracker from worse than raw YOLO on the boat (73% vs 85% of frames tracked well in clear water) into better than it
(88%). On the drone it lifts accuracy from 47–57% to 72–82% when the detector is slow.</div>

<h2>Part I. Midterm proposal (Question 1)</h2>

<h3>1. Topic</h3>
<p><b>Problem.</b> A camera tracker has to decide two things in every frame: <i>which</i> detected box is the target, and
<i>how much</i> to trust it compared with its own prediction. In our current code, both decisions use hand-tuned constants: a
distance gate (<code>GATE = 1.5</code>), a size-ratio window (0.25 to 5), measurement noise R = 60·(0.5/confidence)², and a fixed
process noise Q that was "raised by hand so the filter keeps up when the drone accelerates". These values were tuned for a 30 fps,
1080p drone video. They have no basis in data and do not carry over to another platform.</p>
<p><b>Shared difficulty.</b> Fast vertical motion of the target's box. On our USV logs, the share of frames where YOLO misses the
leader grows from 1.8% to 14.7% as the box's vertical speed rises from 0–2 to 20–40 px per step. The share where YOLO labels the
wrong box as the leader grows from 0.5% to 7.6% (Figure 1).</p>
<p><b>Idea.</b> Treat each hand-tuned decision as a pattern recognition problem and learn it from labelled data:</p>
<table><tr><th style="width:30%">Hand-tuned part</th><th>Replacement from the course</th><th style="width:16%">Chapter</th></tr>
<tr><td>Measurement noise R</td><td>Gaussian maximum-likelihood estimate of the detection error covariance, per axis and per confidence level</td><td>Ch.&nbsp;3-1</td></tr>
<tr><td>Process noise Q</td><td>Maximum-likelihood estimate: closed form from ground-truth trajectories, or by maximising the likelihood of the filter's prediction errors</td><td>Ch.&nbsp;3-1</td></tr>
<tr><td>Gate and ranking score</td><td>Minimum-risk Bayes classifier (target, other object, clutter) with Gaussian class-conditional densities estimated by maximum likelihood</td><td>Ch.&nbsp;2, 3-1</td></tr>
<tr><td>Choice of features</td><td>PCA, Fisher LDA projection and an experimental Hughes curve (accuracy against number of features and training-set size)</td><td>Ch.&nbsp;3-2, Ch.&nbsp;1</td></tr>
<tr><td>Evaluation</td><td>Design cycle, ROC curves, held-out test data</td><td>Ch.&nbsp;1</td></tr></table>

<h3>2. Related papers</h3>
<ol class="small">
<li>R. O. Duda, P. E. Hart, D. G. Stork, <i>Pattern Classification</i>, 2nd ed., Wiley, 2001. Course textbook: Bayes decision theory, MLE, PCA and LDA.</li>
<li>G. F. Hughes, "On the mean accuracy of statistical pattern recognizers," <i>IEEE Trans. Inf. Theory</i>, IT-14, 1968. Accuracy peaks, then falls, as dimension grows.</li>
<li>R. A. Fisher, "The use of multiple measurements in taxonomic problems," <i>Annals of Eugenics</i>, 1936. Fisher's linear discriminant.</li>
<li>R. E. Kalman, "A new approach to linear filtering and prediction problems," <i>J. Basic Engineering</i>, 1960. The Kalman filter as recursive Bayesian estimation.</li>
<li>R. K. Mehra, "On the identification of variances and adaptive Kalman filtering," <i>IEEE Trans. Automatic Control</i>, 1970. Maximum-likelihood estimation of Q and R from innovations.</li>
<li>B. D. Lucas, T. Kanade, "An iterative image registration technique with an application to stereo vision," IJCAI 1981. The optical flow used on both platforms.</li>
<li>Z. Kalal, K. Mikolajczyk, J. Matas, "Forward-backward error: automatic detection of tracking failures," ICPR 2010. The flow check in our tracker.</li>
<li>Y. Bar-Shalom, E. Tse, "Tracking in a cluttered environment with probabilistic data association," <i>Automatica</i>, 1975. Validation gates under clutter.</li>
<li>H. A. P. Blom, Y. Bar-Shalom, "The interacting multiple model algorithm for systems with Markovian switching coefficients," <i>IEEE Trans. Automatic Control</i>, 1988. Switching between motion models.</li>
<li>A. Bewley et al., "Simple online and realtime tracking," ICIP 2016. A detector combined with a Kalman filter and an association step.</li>
<li>C. Guo et al., "On calibration of modern neural networks," ICML 2017. A CNN's confidence score is not a calibrated posterior probability.</li>
</ol>

<h3>3. Project tasks and schedule</h3>
<table><tr><th style="width:4%">#</th><th style="width:28%">Task</th><th>Work</th><th style="width:13%">Status</th></tr>
<tr><td>T1</td><td>Labelled data</td><td>USV: 652 logged runs with exact simulator ground truth. Drone: Grounding DINO labels for two test videos, checked by eye.</td><td>Done</td></tr>
<tr><td>T2</td><td>Detection errors against motion</td><td>Missed and wrong boxes against the target's vertical image speed, on both platforms</td><td>USV done; drone first pass</td></tr>
<tr><td>T3</td><td>MLE of R</td><td>Error covariance per axis and confidence level; check the Gaussian assumption with Q-Q plots</td><td>Done; Q-Q to do</td></tr>
<tr><td>T4</td><td>MLE of Q</td><td>(a) closed form from ground truth (textbook); (b) innovation likelihood (no ground truth needed)</td><td>(b) done; (a) to do</td></tr>
<tr><td>T5</td><td>Bayes gate</td><td>Minimum-risk rule; sweep the loss ratio λ<sub>FA</sub>/λ<sub>miss</sub>; ROC curves; re-acquire the target after a run of rejections</td><td>First version done</td></tr>
<tr><td>T6</td><td>PCA, LDA, Hughes</td><td>2-D Fisher projection of the three classes; PCA explained variance; accuracy against number of features d for n = 20 to 10,000 training samples</td><td>To do</td></tr>
<tr><td>T7</td><td>Tracking replay</td><td>All tracker versions on both platforms, scored against ground truth</td><td>Done</td></tr>
<tr><td>T8</td><td>Closed loop (optional)</td><td>Learned tracker inside the USV formation simulator, huge-wave laps; live drone test if time allows</td><td>Optional</td></tr></table>
<table><tr><th style="width:12%">Week</th><th style="width:22%">Dates</th><th>Work</th></tr>
<tr><td>W1</td><td>Nov 5 – Nov 11</td><td>Proposal; 3-minute proposal talk (Nov 11)</td></tr>
<tr><td>W2</td><td>Nov 12 – Nov 18</td><td>T4(a) closed-form Q; T3 Q-Q plots; a latency-aware R fit</td></tr>
<tr><td>W3</td><td>Nov 19 – Nov 25</td><td>T5 loss sweep, ROC, re-acquisition</td></tr>
<tr><td>W4</td><td>Nov 26 – Dec 2</td><td>T6 PCA, LDA, Hughes curve</td></tr>
<tr><td>W5</td><td>Dec 3 – Dec 9</td><td>T2 drone motion analysis with smoothed ground truth; more drone test videos</td></tr>
<tr><td>W6</td><td>Dec 10 – Dec 16</td><td>T8 optional closed-loop runs</td></tr>
<tr><td>W7</td><td>Dec 17 – Dec 23</td><td>Report, figures, comparison videos</td></tr>
<tr><td>W8</td><td>Dec 24 → final</td><td>Rehearsal; spare time</td></tr></table>
<p class="small">The final presentation date is still to be confirmed; we will move the last two weeks to fit it.</p>

<h3>4. Final product</h3>
<ol><li><b>A shared Python module</b> with three parts: a Bayes gate, a noise model (R and Q learned by MLE), and a feature
analysis (PCA and LDA). It replaces the hand-tuned constants in both trackers.</li>
<li><b>Two labelled datasets</b>: USV candidate boxes with exact ground truth in six weather conditions, and drone videos with
checked pseudo ground truth.</li>
<li><b>A reproducible evaluation</b>: a deterministic replay of the tracker on both platforms, with all figures and tables in this report.</li>
<li><b>Side-by-side videos</b>: YOLO only against the learned tracker, for the drone and for a huge-wave boat run.</li></ol>

<h3>5. Project report: components and items</h3>
<p>Abstract; introduction (fast vertical image motion: a moving target on the drone, a moving camera on the USV); related work;
problem formulation (classes, feature vector, loss matrix, the minimum-risk rule derived as a likelihood-ratio inequality);
method (MLE of R and Q with derivations, Bayes gate, PCA and LDA); data and ground truth; results on each platform, then
compared; discussion (when the Gaussian assumption fails, dimension against sample size, limitations); conclusion and future
work; references; appendix with code and reproduction steps.</p>

<h3>6. Project presentation (about 15 minutes, both members)</h3>
<p>Motivation with two video clips, drone and boat (2 min) → the shared pipeline and its hand-tuned parts (2 min) → the
pattern recognition formulation linked to the lecture slides (3 min) → USV results (3 min) → drone results (3 min) →
cross-platform conclusion and questions (2 min). Details are in Part IV.</p>

<h2 class="part">Part II. Proposed method</h2>

<h3>II.1 System and notation</h3>
<div class="pipe">
<div class="n">Camera frame</div><div class="a">→</div>
<div class="n">YOLOv8<br>candidate boxes</div><div class="a">→</div>
<div class="n pr">Accept or reject<br><span class="tag">Bayes rule, Ch. 2</span></div><div class="a">→</div>
<div class="n pr">Kalman filter + optical flow<br><span class="tag">MLE of R and Q, Ch. 3-1</span></div><div class="a">→</div>
<div class="n">Target box<br>→ controller</div></div>
<p class="cap">Figure 0. The shared tracker. Blue boxes are where the course methods replace hand-tuned constants.</p>
<p>The filter state is x = (c<sub>x</sub>, c<sub>y</sub>, w, h, v<sub>x</sub>, v<sub>y</sub>, v<sub>w</sub>, v<sub>h</sub>)<sup>t</sup>,
with a constant-velocity transition F. A measurement z = Hx + v (a YOLO box or a flow-shifted box) has noise v ~ N(0, R). The
motion model is x<sub>k+1</sub> = Fx<sub>k</sub> + w<sub>k</sub>, with w<sub>k</sub> ~ N(0, Q). Errors are measured in units of
box size, so one model works for both near and far targets.</p>

<h3>II.2 Method 1: maximum-likelihood estimate of the measurement noise R (Ch. 3-1)</h3>
<p>For each training detection that matches the true box, the error is e<sub>k</sub> = (z<sub>k</sub> − z<sub>k</sub><sup>true</sup>)/size.
With e ~ N(μ, Σ), the slides' Gaussian case with unknown μ and Σ gives the closed-form MLE:</p>
<div class="eq">μ̂ = (1/n) Σ<sub>k</sub> e<sub>k</sub>, &nbsp;&nbsp; Σ̂ = (1/n) Σ<sub>k</sub> (e<sub>k</sub> − μ̂)(e<sub>k</sub> − μ̂)<sup>t</sup></div>
<p>We fit Σ̂ separately for the horizontal and vertical axes and for each YOLO-confidence bin. This tests the drone code's
assumption that a single variance, scaled by confidence, holds on both axes.</p>

<h3>II.3 Method 2: maximum-likelihood estimate of the process noise Q (Ch. 3-1)</h3>
<p><b>(a) With ground truth: closed form, as in the textbook.</b> From the true box trajectory, the process residuals are
w<sub>k</sub> = x<sub>k+1</sub> − Fx<sub>k</sub>, and the MLE is Q̂ = (1/n) Σ<sub>k</sub> w<sub>k</sub>w<sub>k</sub><sup>t</sup>.
This is the same derivation as for R, applied to the motion instead of the measurement.</p>
<p><b>(b) Without ground truth: innovation likelihood</b> (Mehra, 1970). For a correct model, the innovations
ν<sub>k</sub> = z<sub>k</sub> − Hx̂<sub>k|k−1</sub> are independent, with ν<sub>k</sub> ~ N(0, S<sub>k</sub>), where S<sub>k</sub> = HP<sub>k|k−1</sub>H<sup>t</sup> + R. So we choose Q to maximise</p>
<div class="eq">ℓ(Q) = Σ<sub>k</sub> ln N(ν<sub>k</sub>; 0, S<sub>k</sub>(Q)) = −½ Σ<sub>k</sub> [ ν<sub>k</sub><sup>t</sup>S<sub>k</sub><sup>−1</sup>ν<sub>k</sub> + ln|S<sub>k</sub>| + d ln 2π ]</div>
<p>This is the Ch. 3-1 principle: the observed samples are the innovations, and Q is the parameter. Because S<sub>k</sub> depends
on Q through the filter's recursion, there is no closed-form solution, so we maximise over a grid. Method (b) is what runs on a
real drone or boat. Method (a) is the textbook check when ground truth exists. The final presentation will compare the two.</p>

<h3>II.4 Method 3: minimum-risk Bayes rule for accepting a detection (Ch. 2)</h3>
<p>Each candidate box gives a feature vector <b>x</b>: YOLO confidence, Mahalanobis distance to the predicted box under the
filter's covariance, log area ratio and log aspect ratio. Classes: ω<sub>1</sub> = target, ω<sub>2</sub> = not the target.
λ<sub>ij</sub> is the loss of deciding ω<sub>i</sub> when the truth is ω<sub>j</sub>. Accepting a false box (λ<sub>12</sub>)
costs more than rejecting a true one (λ<sub>21</sub>), because the filter can coast on its prediction for a few frames.
Minimising the conditional risk R(α<sub>i</sub>|x) = Σ<sub>j</sub> λ<sub>ij</sub>P(ω<sub>j</sub>|x) gives the rule: accept if</p>
<div class="eq">p(x|ω<sub>1</sub>) / p(x|ω<sub>2</sub>) &gt; [(λ<sub>12</sub> − λ<sub>22</sub>) / (λ<sub>21</sub> − λ<sub>11</sub>)] · P(ω<sub>2</sub>) / P(ω<sub>1</sub>)</div>
<p>The class-conditional densities p(x|ω<sub>i</sub>) are Gaussians fitted by MLE, as in Method 1. The priors P(ω<sub>i</sub>)
are estimated per platform and per condition. Distance is measured with the filter's own covariance, so the acceptance region
widens automatically while the tracker coasts. This replaces the hand-tuned gate growth of (1 + 0.15·misses).</p>

<h3>II.5 Method 4: feature analysis with PCA, Fisher LDA and the Hughes effect (Ch. 3-2, Ch. 1)</h3>
<p>Project the candidate features of the three classes (target, other object, clutter) onto the 2-D Fisher subspace (c − 1 = 2
dimensions) for each condition, and show PCA's explained variance. Then measure Bayes-gate accuracy against the number of
features d (1 to 9) for training sizes n = 20, 100, 1,000 and 10,000. This reproduces the Hughes peaking effect on our own data
and justifies the final feature set.</p>

<h3>II.6 Evaluation protocol</h3>
<ul>
<li><b>Deterministic replay.</b> His real-time tracker is replayed frame by frame. A YOLO result requested at frame i arrives
at frame i + L. L = 1 matches his GPU (YOLO takes 11 ms; a frame lasts 33 ms); L = 3 imitates a slower onboard computer. On the
USV, L is one 100 ms control step. The replay reproduces his reported YOLO detection rate of 83% on testv4.</li>
<li><b>Ground truth.</b> USV: the simulator's true leader box. Drone: Grounding DINO (2 prompts × horizontal flip = 4 opinions,
fused with his own labelling rule, <i>without</i> YOLO as an opinion so the labels are independent of the model under test),
checked by eye on contact sheets.</li>
<li><b>Training and test data are separate.</b> Drone: trained on one video, tested on the other. USV: runs split by
random seed into two folds.</li>
<li><b>Measures.</b> Share of frames with IoU ≥ 0.5 against the true box; the same on the 20% of frames with the fastest
vertical motion; wrong-target frames; jitter.</li></ul>

<h2>Part III. Preliminary results</h2>

<h3>III.1 Fast vertical motion breaks detection on the USV</h3>
<div class="fig">{svg("fig_usv_motion")}</div>
<p class="cap">Figure 1. USV, weather-trained YOLO, 259,000 frames. Both error types rise steeply once the box moves more than
10 px per step. In huge waves the median vertical speed doubles (6 vs 3 px per step).</p>
<p>On the drone videos there is no clear trend: misses stay between 7% and 13% at every speed. Drone misses cluster on hard
backgrounds instead, such as plants and the white tiled wall in IMG_7888. The per-frame speed is also noisy because the
pseudo ground truth jitters. Smoothing and normalising by box size is planned (T2).</p>

<h3>III.2 MLE of R: the drone code's noise model is wrong on the vertical axis</h3>
<div class="fig">{svg("fig_usv_R")}</div>
<p class="cap">Figure 2. USV detection error variance (MLE) by YOLO confidence. Horizontal variance falls about 20× as
confidence rises. Vertical variance barely changes, and the vertical error has a constant offset of about +0.09 box heights.</p>
<p>The drone code uses one variance for both axes, scaled by (0.5/confidence)². That roughly fits the horizontal axis but not
the vertical one. On the USV, maximum likelihood also shows that optical flow's vertical error variance is about 4× YOLO's
(0.045 vs 0.011 box sizes²). So on the boat, flow should carry less weight than YOLO.</p>

<h3>III.3 MLE of Q: the likelihood peaks at 10× the drone setting on the USV</h3>
<div class="fig">{svg("fig_q_likelihood")}</div>
<p class="cap">Figure 3. USV training fold 0: mean innovation log-likelihood for each candidate Q. Both folds and both R
choices peak at 10×. Learned R also gives a higher likelihood than the hand-tuned R (−11.2 vs −12.3), so it describes the data better.</p>
<p>The peak is what the frame rates predict. The drone runs at 30 fps and the boat camera at 10 Hz, so the box moves about 3× as
far per step on the boat, and the variance of that motion is about 9× larger. On the drone, the likelihood was still rising at
the largest Q tried (100×), so the grid must be widened.</p>

<h3>III.4 Tracking accuracy on the USV</h3>
<div class="fig">{svg("fig_usv_tracking")}</div>
<p class="cap">Figure 4. USV, 64 camera sequences, two folds split by seed. Frames tracked with IoU ≥ 0.5.</p>
{usv_tab}
<p class="small">Each cell: all frames / <span class="fast">fastest 20% of frames</span>, in % of frames with IoU ≥ 0.5. Bold = best in the row.</p>

<h3>III.5 Tracking accuracy on the drone</h3>
<div class="fig">{svg("fig_drone_tracking")}</div>
<p class="cap">Figure 5. Drone, cross-video: trained on one video, tested on the other. Frames tracked with IoU ≥ 0.5.</p>
{drone_tab}
<p class="small">Each cell: all frames / <span class="fast">fastest 20% of frames</span>, in %. On IMG_7888 with a 1-frame delay, the
Bayes gate cuts wrong-target frames from {wl("L1|img7888", "his"):.1f}% (hand-tuned) to {wl("L1|img7888", "bayes_gate+learned_RQ"):.1f}%.</p>

<h3>III.6 Is the improvement real? Statistical tests and videos</h3>
<p><b>USV.</b> Each of the 64 camera sequences is one paired sample (hand-tuned and learned Q run on the same frames). The learned Q
came from training runs that never include the test sequence. Wilcoxon signed-rank test on the per-sequence share of well-tracked frames:</p>
<table class="res"><tr><th>Condition</th><th>Sequences</th><th>Learned Q better than hand-tuned</th><th>Median gain (points)</th><th>p</th>
<th>Learned Q better than YOLO only</th><th>Median gain (points)</th><th>p</th></tr>{usv_stats}</table>
<p><b>Drone.</b> Two videos, so we resample 1-second blocks of frames (block bootstrap, 4,000 resamples) to get a 95% confidence
interval for the gain in the share of well-tracked frames:</p>
<table class="res"><tr><th>Test video</th><th>Learned Q − hand-tuned, points [95% CI]</th><th>1-s blocks better / worse</th><th>Learned Q − YOLO only, points [95% CI]</th></tr>{drone_stats}</table>
<div class="box"><b>Verdict.</b> Against the hand-tuned tracker, the learned Q is better on <b>every one of the 64 boat sequences</b>
(p = {EV['usv']['all']['p_vs_hand']:.1g}). On the drone it is better in all four cases, and in three the 95% interval excludes zero.
With a slow detector the gain is about +25 points. Against raw YOLO, the learned tracker wins clearly in clear water, rain and
night + rain, and when the drone's detector is slow. It is no better than YOLO in huge waves (p = {EV['usv']['huge_waves']['p_vs_yolo']:.1g}) and
<b>worse than YOLO in the dark storm</b> on all 8 sequences. That case is the main open problem for the final presentation.</div>
<p><b>Detection videos</b> (folder <code>Experiments/PR_Course/rollouts/</code>). Each video shows three panels side by side: YOLO only, the
hand-tuned drone tracker, and the drone tracker with learned Q. Green is the ground truth; each panel shows its current IoU and
its running share of well-tracked frames.</p>
<table><tr><th>File</th><th>What it shows</th></tr>
<tr><td><code>drone_testv4_delay3.mp4</code>, <code>drone_img7888_delay3.mp4</code></td><td>Drone with a slow detector (3-frame delay): the hand-tuned box lags behind fast climbs and drops; the learned-Q box stays on the drone.</td></tr>
<tr><td><code>drone_testv4_delay1.mp4</code>, <code>drone_img7888_delay1.mp4</code></td><td>Drone with the teammate's real delay: smaller gain (about +3 points).</td></tr></table>
<table class="res"><tr><th>USV video (cropped around the leader)</th><th>YOLO only</th><th>Hand-tuned</th><th>Learned Q</th></tr>{vid_rows}</table>
<p class="small">The USV clips are the sequences with the largest gain in huge waves and in clear water, plus a typical
(median-gain) dark-storm sequence, where learned Q improves on the hand-tuned tracker but stays below YOLO. The simulator's
truth box sits on average about 0.1 box heights above YOLO's box in every condition. It is aligned in time (the best match is
at a 0-step offset), and it lowers every tracker's IoU equally. In huge waves, single frames can show a larger mismatch.</p>

<h3>III.7 What the results show</h3>
<ol>
<li><b>Hand-tuned constants do not transfer.</b> The drone tracker, tuned on drone video, is worse than raw YOLO on the USV in every condition.</li>
<li><b>MLE-learned Q is the one change that helps on both platforms.</b> On the USV it beats the hand-tuned tracker on all 64 sequences, beats raw YOLO in clear, rain, night and
night + rain, ties with YOLO in huge waves, and loses to it in the dark storm. In the fastest huge-wave frames it more
than doubles the share of well-tracked frames in the fastest huge-wave frames (9.5% → 22.6%). On the drone with a slow
detector it raises accuracy from 47–57% to 72–82%.</li>
<li><b>Learned R helps only in some cases.</b> It helps on the drone with a 1-frame delay, but hurts with a 3-frame delay and on
the USV. The fit compares each box with ground truth at the frame the image was taken, but the filter uses the box L frames
later. A latency-aware fit is planned.</li>
<li><b>The Bayes gate depends on the platform.</b> On the drone, which has real distractors, it gives the best accuracy in fast
frames (96% on testv4) and halves wrong locks on IMG_7888. On the USV, wrong leader boxes are rare (2.2% of candidates). Rejecting
true boxes then causes drift, so the gate lowers accuracy. A loss-ratio sweep and target re-acquisition are planned.</li>
<li><b>There is a trade-off between lag and smoothness.</b> The learned trackers follow the target more closely but jitter more
(USV clear: 1.6 → 1.9 px; drone testv4: 9 → 21–25 px).</li></ol>
<div class="warn"><b>Limitations of these results.</b> There are only two drone videos, so the drone results come from two
folds and are not significance-tested. Drone ground truth comes from Grounding DINO, not hand labels; frames where it was
unsure (12% and 6%) are not scored. The USV results are simulation only and offline, with no closed-loop formation runs yet.
Q was chosen from a grid.</div>

<h2>Part IV. Plan for the final presentation</h2>
<h3>IV.1 Remaining experiments, in order of value per effort</h3>
<table><tr><th style="width:4%">#</th><th>Experiment</th><th style="width:30%">What it adds</th><th style="width:12%">Effort</th></tr>
<tr><td>1</td><td>Closed-form Q from ground truth (Method 2a) on both platforms, compared with the innovation-likelihood Q</td><td>The textbook MLE derivation on a slide; checks the grid result</td><td>Half a day</td></tr>
<tr><td>2</td><td>Wider Q grid on the drone; latency-aware R fit</td><td>Fixes the two known gaps in the current results</td><td>Half a day</td></tr>
<tr><td>3</td><td>Loss sweep λ<sub>12</sub>/λ<sub>21</sub> = 0.1 to 20 with ROC curves; re-acquire the target after k rejections</td><td>Shows Ch. 2 decision theory directly; fixes the USV gate</td><td>1 day</td></tr>
<tr><td>4</td><td>PCA and 2-D Fisher LDA plots of the three classes; Hughes curve</td><td>Covers Ch. 3-2 and the dimensionality material</td><td>1 day</td></tr>
<tr><td>5</td><td>Q-Q plots of the errors; mixture model if they are not Gaussian</td><td>Tests the Gaussian assumption behind every method</td><td>Half a day</td></tr>
<tr><td>6</td><td>Drone: more test videos; smoothed motion analysis</td><td>Makes the drone result stronger than two folds</td><td>Drone member</td></tr>
<tr><td>7</td><td>Optional: learned Q inside the USV formation simulator (huge-wave laps, 3 seeds)</td><td>Effect on formation error, not just box accuracy</td><td>1–2 days</td></tr></table>

<h3>IV.2 Slide outline (about 15 minutes)</h3>
<table><tr><th style="width:8%">Slide</th><th>Content</th><th style="width:14%">Speaker</th></tr>
<tr><td>1–2</td><td>Two clips: a drone climbing fast and a boat camera in huge waves. Same failure: the box jumps vertically and YOLO misses it.</td><td>Both</td></tr>
<tr><td>3</td><td>The shared pipeline (Figure 0) and its hand-tuned constants</td><td>Drone</td></tr>
<tr><td>4–6</td><td>Theory: Gaussian MLE (Σ̂ derivation) → R and Q; the minimum-risk rule as a likelihood-ratio inequality; Fisher LDA</td><td>USV</td></tr>
<tr><td>7</td><td>Data and ground truth; evaluation protocol</td><td>Both</td></tr>
<tr><td>8–9</td><td>USV: Figures 1–4 and the likelihood peak at 10×</td><td>USV</td></tr>
<tr><td>10–11</td><td>Drone: Figure 5, the Bayes gate in fast frames, side-by-side video</td><td>Drone</td></tr>
<tr><td>12</td><td>LDA projection and Hughes curve</td><td>USV</td></tr>
<tr><td>13</td><td>What transfers between platforms (learned parameters) and what does not (hand-tuned constants, optical flow on a 40 px boat)</td><td>Both</td></tr>
<tr><td>14</td><td>Limitations and future work; questions</td><td>Both</td></tr></table>

<h3>IV.3 Proposal talk on Nov 11 (3 minutes, 5 slides)</h3>
<ol class="small"><li>Problem: two platforms, one failure (video stills, Figure 1).</li>
<li>The pipeline and its hand-tuned constants (Figure 0).</li>
<li>Methods from the course: MLE of R and Q, the minimum-risk rule, PCA/LDA (Part II equations).</li>
<li>First result: hand-tuned against learned Q on both platforms (Figures 4 and 5).</li>
<li>Schedule and final deliverables (Part I, items 3 and 4).</li></ol>

<h3>Appendix: data and code</h3>
<p class="small">Code: <code>Tools/pr_course/</code> (USV), <code>Tools/pr_course/drone/</code> (drone replay, labelling, analysis), <code>Tools/pr_course/report/</code> (this report). Data and result files: <code>Experiments/PR_Course/</code>. The drone tracker is the teammate's <code>track.py</code>, ported with its constants unchanged.</p>
</body></html>"""

os.makedirs(B, exist_ok=True)
open(f"{B}/report.html", "w").write(html)
subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={PDF}",
                f"file://{os.path.abspath(B)}/report.html"], check=True, capture_output=True)
print("wrote", PDF)

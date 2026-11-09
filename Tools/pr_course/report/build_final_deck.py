"""Fill the group's Google Slides export with the final-presentation content (professional theme).
Usage: python build_final_deck.py IN.pptx OUT.pptx MEDIA_DIR REPO_ROOT
IN.pptx = File > Download > .pptx of the group deck (keeps its 7 section slides and the HOG paper image).
MEDIA_DIR holds the example frames (rendered from Experiments/PR_Course by the session that built the deck)."""
import json, sys
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

IN, OUT, MEDIA, ROOT = sys.argv[1:5]
HEAD, BODY = "Cambria", "Calibri"
hexc = RGBColor.from_string
NAVY, NAVY2, INK, MUTED = hexc("0B1F3A"), hexc("16345F"), hexc("1F2933"), hexc("5B6573")
CARD, LINE, KICK, WHITE = hexc("F3F5F8"), hexc("D5DAE1"), hexc("0E7490"), hexc("FFFFFF")
ICE, MINT = hexc("C9D6EA"), hexc("7DD3C0")
TRAD, YOLO, LQ, HAND, GREEN = hexc("EB6834"), hexc("2A78D6"), hexc("1BAF7A"), hexc("EDA100"), hexc("3CC850")
BEST = hexc("E3F5EE")
FOOTER = "Lab412  ·  Traditional Pattern Recognition vs. YOLOv8"

# ---------------------------------------------------------------- data
usv = json.load(open(f"{ROOT}/Experiments/PR_Course/classic/eval.json"))["groups"]
dr_classic = json.load(open(f"{ROOT}/Experiments/PR_Course/classic/drone/drone_report.json"))
dr_yolo = json.load(open(f"{ROOT}/Experiments/PR_Course/drone/drone_report.json"))["results"]
COND = [("clear", "Clear"), ("rain", "Rain"), ("night", "Night"), ("night_rain", "Night+rain"),
        ("dark_storm", "Dark storm"), ("huge_waves", "Huge waves")]
VIDS = [("testv4", "testv4"), ("img7888", "IMG_7888"), ("img7923", "Tello (held out)")]
TELLO_YOLO = {1: dict(only=33.0, hand=46.5, lq=70.3), 3: dict(only=20.8, hand=39.4, lq=57.8)}  # new_video_eval.py


def dy(v, L, arm):
    if v == "img7923":
        return TELLO_YOLO[L][arm]
    return dr_yolo[f"L{L}|{v}|" + {"only": "yolo_only", "hand": "his", "lq": "his+learned_Q"}[arm]]["all"]["success50"]


def dc(v, L, arm):
    return dr_classic["results"][f"L{L}|{v}"]["classic_" + {"only": "only", "hand": "hand", "lq": "learnedQ"}[arm]]


# ---------------------------------------------------------------- helpers
prs = Presentation(IN)
LAYOUT = prs.slide_layouts.get_by_name("TITLE_AND_BODY")


def style_title(shape, text, size=24, color=NAVY, box=(0.4, 0.5, 9.2, 0.62), align=PP_ALIGN.LEFT, bold=False):
    tf = shape.text_frame; tf.clear()
    bp = tf._txBody.find(qn("a:bodyPr"))
    for ch in list(bp):
        bp.remove(ch)
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0)
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = line
        r.font.name = HEAD; r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
    shape.left, shape.top, shape.width, shape.height = (Inches(v) for v in box)
    tf.vertical_anchor = MSO_ANCHOR.TOP


def drop_nontitle(slide):
    for sh in list(slide.placeholders):
        if sh.placeholder_format.idx != 0:
            sh._element.getparent().remove(sh._element)


def text(slide, x, y, w, h, paras, size=14, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=6,
         font=BODY, name=None, spacing=None):
    """paras: str | list of runs (str or (text, opts)) | dict(runs=..., bullet=True). opts: bold, italic, color, size, font."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name: tb.name = name
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.04); tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        bullet = False
        if isinstance(para, dict):
            bullet = para.get("bullet", False); para = para["runs"]
        runs = [(para, {})] if isinstance(para, str) else [(r, {}) if isinstance(r, str) else r for r in para]
        p.alignment = align; p.space_after = Pt(space)
        if bullet:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.2))); pPr.set("indent", str(-Inches(0.18)))
            bc = pPr.makeelement(qn("a:buClr"), {}); sc = bc.makeelement(qn("a:srgbClr"), {"val": "5B6573"}); bc.append(sc)
            pPr.append(bc)
            pPr.append(pPr.makeelement(qn("a:buChar"), {"char": "•"}))
        for t, o in runs:
            r = p.add_run(); r.text = t
            f = r.font; f.name = o.get("font", font); f.size = Pt(o.get("size", size)); f.bold = o.get("bold", False)
            f.italic = o.get("italic", False); f.color.rgb = o.get("color", color)
            if spacing:
                r._r.get_or_add_rPr().set("spc", str(spacing))
    return tb


def box(slide, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=None, radius=0.07):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name: s.name = name
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line; s.line.width = Pt(1.25)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / max(min(w, h), 0.1))
    return s


def dot(slide, x, y, color, d=0.2):
    return box(slide, x, y, d, d, fill=color, shape=MSO_SHAPE.OVAL)


def badge(slide, x, y, label, color, d=0.42, size=14):
    dot(slide, x, y, color, d)
    text(slide, x, y, d, d, [[(label, dict(bold=True, color=WHITE))]], size=size, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def arrow(slide, x1, y1, x2, y2, color=MUTED, width=1.75, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color; c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    if dash:
        ln.append(ln.makeelement(qn("a:prstDash"), {"val": "dash"}))
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return c


def chip(slide, x, y, color, label, size=12, w=1.6, txt=INK):
    dot(slide, x, y + 0.06, color, 0.15)
    text(slide, x + 0.2, y - 0.02, w, 0.3, [label], size=size, color=txt)


def bar_chart(slide, x, y, w, h, cats, series, label_size=11):
    cd = CategoryChartData(); cd.categories = cats
    for name, vals, _ in series:
        cd.add_series(name, vals)
    ch = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd).chart
    ch.font.name = BODY; ch.font.size = Pt(11); ch.font.color.rgb = INK
    ch.has_title = False
    plot = ch.plots[0]; plot.gap_width = 60; plot.overlap = -10
    plot.has_data_labels = True
    dl = plot.data_labels; dl.number_format = "0"; dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END; dl.font.size = Pt(label_size); dl.font.color.rgb = INK; dl.font.name = BODY
    for s, (_, _, col) in zip(plot.series, series):
        s.format.fill.solid(); s.format.fill.fore_color.rgb = col; s.format.line.fill.background()
    va = ch.value_axis; va.maximum_scale = 100; va.minimum_scale = 0; va.major_unit = 25
    va.has_major_gridlines = True; va.major_gridlines.format.line.color.rgb = hexc("E6E9EE")
    va.format.line.fill.background(); va.tick_labels.font.size = Pt(10); va.tick_labels.font.color.rgb = MUTED
    va.tick_labels.number_format = '0"%"'; va.tick_labels.number_format_is_linked = False
    ca = ch.category_axis; ca.tick_labels.font.size = Pt(11); ca.tick_labels.font.color.rgb = INK
    ca.format.line.color.rgb = LINE; ca.has_major_gridlines = False
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11); ch.legend.font.name = BODY; ch.legend.font.color.rgb = INK
    return ch


def stat(slide, x, y, big, small, color=NAVY, w=2.9):
    text(slide, x, y, w, 0.55, [[(big, dict(bold=True, size=28, color=color, font=HEAD))]])
    text(slide, x, y + 0.58, w, 0.75, [small], size=12, color=MUTED)


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def picture(slide, path, x, y, w=None, h=None, name=None, crop=None):
    """crop = (left, top, right, bottom) fractions to trim."""
    p = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if crop:
        p.crop_left, p.crop_top, p.crop_right, p.crop_bottom = crop
    if name: p.name = name
    p.line.color.rgb = LINE; p.line.width = Pt(0.75)
    return p


def dark(slide):
    bg = slide.background.fill; bg.solid(); bg.fore_color.rgb = NAVY


def frame(slide, kicker, title):
    """Light content slide: kicker label, title, footer."""
    drop_nontitle(slide)
    text(slide, 0.4, 0.22, 9.2, 0.3, [[(kicker.upper(), dict(bold=True, color=KICK))]], size=10, spacing=150, name="Kicker")
    style_title(slide.shapes.title, title)


def new_slide():
    return prs.slides.add_slide(LAYOUT)


S = list(prs.slides)
s_title, s_intro, s_rel, s_method, s_setup, s_result, s_disc = S

# ================================================================ 1 Title (dark, keeps the group's title text)
dark(s_title)
title_text = s_title.shapes.title.text_frame.text
style_title(s_title.shapes.title, title_text, size=30, color=WHITE, box=(0.55, 1.15, 5.4, 2.2), bold=True)
sub = [sh for sh in s_title.placeholders if sh.placeholder_format.idx != 0][0]
style_title(sub, "Lab412", size=18, color=ICE, box=(0.55, 3.55, 5.0, 0.4))
for p in sub.text_frame.paragraphs:
    for r in p.runs:
        r.font.name = BODY
text(s_title, 0.55, 0.65, 5.4, 0.3, [[("PATTERN RECOGNITION  ·  FINAL PROJECT", dict(bold=True, color=MINT))]], size=11, spacing=200)
text(s_title, 0.55, 4.25, 5.4, 0.7, [[("Drone video and USV simulator  ·  YOLOv8 vs. a detector built from course methods", dict(color=ICE))]],
     size=13)
im = Image.open(f"{MEDIA}/intro_drone.jpg"); W, H = im.size          # half-bleed photo, cropped around the drone
target = 4.0 / 5.625; cw = H * target; cx = W * 0.5
pic = s_title.shapes.add_picture(f"{MEDIA}/intro_drone.jpg", Inches(6.0), 0, Inches(4.0), Inches(5.625))
l = max(0.0, (cx - cw / 2) / W); pic.crop_left, pic.crop_right = l, max(0.0, 1 - l - cw / W)
pic.name = "Title photo"
notes(s_title, "Our question: for detecting and tracking a small target in video, is a detector built only from classical "
      "pattern-recognition methods good enough, or do we need YOLOv8 - and can classical methods still help YOLOv8? "
      "We test on two platforms: a small drone filmed from the ground, and the leader boat seen from a follower USV.")

# ================================================================ 2 Introduction
frame(s_intro, "Introduction", "Two Questions About Small-Target Detection")
picture(s_intro, f"{MEDIA}/intro_drone.jpg", 0.4, 1.3, w=4.4, name="Drone frame")
picture(s_intro, f"{MEDIA}/intro_usv.jpg", 0.4, 3.85, w=2.1, name="USV frame")
text(s_intro, 2.65, 3.82, 2.15, 1.3, [[("Same pipeline, two targets", dict(bold=True, color=INK))],
     "Top: drone filmed from the ground. Left: leader boat seen by a follower USV in waves."], size=11, color=MUTED, space=3)
text(s_intro, 5.1, 1.25, 4.5, 0.95, [[("Goal: ", dict(bold=True)), ("find and follow one small target in every frame, even "
     "when its box jumps up and down (the drone climbs, the boat camera pitches in waves).", {})]], size=14)
for i, (q, sub_t, col) in enumerate([
        ("Can traditional pattern recognition replace YOLOv8?", "Traditional detector  vs.  YOLOv8", TRAD),
        ("Can traditional methods improve YOLOv8?", "YOLOv8  vs.  YOLOv8 + MLE-learned tracker", LQ)]):
    yy = 2.3 + i * 1.42
    box(s_intro, 5.1, yy, 4.5, 1.25, name=f"Question {i + 1}")
    badge(s_intro, 5.28, yy + 0.2, f"Q{i + 1}", col, d=0.5, size=13)
    text(s_intro, 5.92, yy + 0.14, 3.6, 0.6, [[(q, dict(bold=True))]], size=15)
    text(s_intro, 5.92, yy + 0.8, 3.6, 0.35, [sub_t], size=12, color=MUTED)
notes(s_intro, "Both of our targets are small in the image and move fast vertically. YOLOv8 is the usual answer for detection. "
      "We ask two questions. Q1: if we build the detector only from what we learned in this course - Fisher LDA, PCA, "
      "Gaussian maximum likelihood, Bayes decision - how close do we get to YOLOv8? Q2: if we keep YOLOv8, can the same "
      "course methods make the tracking after the detector better than hand-tuned constants?")

# ================================================================ 3 Related work (keeps the HOG picture)
frame(s_rel, "Background", "Related Work")
pic = [sh for sh in s_rel.shapes if sh.shape_type == 13][0]
ph = 4.1 * 1857400 / 3661525
pic.left, pic.top, pic.width, pic.height = Inches(0.4), Inches(1.3), Inches(4.1), Emu(int(Inches(4.1) * 1857400 / 3661525))
pic.line.color.rgb = LINE; pic.line.width = Pt(0.75)
text(s_rel, 0.4, 1.3 + ph + 0.12, 4.1, 1.2, [[("Dalal & Triggs, CVPR 2005. ", dict(bold=True, color=INK)),
     ("Hand-designed features + a linear classifier, scanned over the image: the classic detector that CNNs replaced. "
      "Our traditional detector follows the same recipe.", {})]], size=12, color=MUTED)
refs = [("Fisher 1936; Belhumeur et al., TPAMI 1997", "Fisher linear discriminant; PCA + LDA (\"Fisherfaces\")", TRAD),
        ("Duda, Hart & Stork 2001; Hughes 1968", "Bayes decision, Gaussian MLE; too many dimensions for the data", TRAD),
        ("Redmon et al., CVPR 2016; Jocher et al. 2023", "YOLO one-stage CNN detector; YOLOv8 (Ultralytics)", YOLO),
        ("Kalman 1960; Lucas & Kanade 1981", "Kalman filter and optical flow between detections", LQ),
        ("Mehra, IEEE TAC 1970", "Learning the Kalman noise Q, R from the innovations", LQ)]
for i, (a, b, col) in enumerate(refs):
    yy = 1.3 + i * 0.74
    dot(s_rel, 4.85, yy + 0.08, col, 0.14)
    text(s_rel, 5.08, yy, 4.5, 0.7, [[(a, dict(bold=True, size=13))], [(b, dict(color=MUTED, size=12))]], space=1)
chip(s_rel, 5.08, 5.0 - 0.1, TRAD, "traditional detector", size=10, w=1.5)
chip(s_rel, 6.65, 5.0 - 0.1, YOLO, "deep detector", size=10, w=1.1)
chip(s_rel, 7.85, 5.0 - 0.1, LQ, "tracking", size=10, w=1.0)
notes(s_rel, "Dalal and Triggs is the reference point for traditional detection: fixed features, a linear classifier and a "
      "sliding window. We build the same kind of detector from course methods: Fisher's discriminant instead of an SVM, PCA "
      "and a Gaussian Bayes classifier. YOLO is the deep-learning alternative. For tracking we use the Kalman filter with "
      "optical flow, and Mehra's idea of learning the filter noise from its innovations.")

# ================================================================ 4 USV fleet (new)
s_fleet = new_slide()
frame(s_fleet, "Platform", "How the USV Fleet Uses the Detector")
# top view of the formation (not to scale)
box(s_fleet, 0.4, 1.3, 3.3, 3.8, name="Formation panel")
text(s_fleet, 0.55, 1.38, 3.0, 0.3, [[("Formation, top view", dict(bold=True))]], size=12)
def boat(x, y, w, h, col, label, sub_l, side=False):
    b = s_fleet.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = col; b.line.fill.background(); b.shadow.inherit = False
    b.name = label
    if side:   # label to the right, clear of the camera arrows
        text(s_fleet, x + w + 0.1, y + 0.05, 1.2, 0.5, [[(label, dict(bold=True, size=11))], [(sub_l, dict(size=10, color=MUTED))]], space=0)
    else:
        text(s_fleet, x - 0.6, y + h + 0.03, w + 1.2, 0.5, [[(label, dict(bold=True, size=11))], [(sub_l, dict(size=10, color=MUTED))]],
             align=PP_ALIGN.CENTER, space=0)
boat(1.5, 1.9, 0.46, 0.62, NAVY, "Leader", "drives a set route", side=True)
boat(0.92, 3.55, 0.36, 0.5, YOLO, "Follower L", "camera only")
boat(2.82, 3.55, 0.36, 0.5, YOLO, "Follower R", "camera only")
arrow(s_fleet, 1.12, 3.5, 1.6, 2.62, color=YOLO, width=1.25, dash=True)
arrow(s_fleet, 2.98, 3.5, 1.88, 2.62, color=YOLO, width=1.25, dash=True)
text(s_fleet, 0.55, 4.72, 3.0, 0.3, ["about 22 m behind, 13 m to each side"], size=10, color=MUTED, align=PP_ALIGN.CENTER)
# camera view + loop
picture(s_fleet, f"{MEDIA}/fleet_camera.jpg", 3.95, 1.3, w=3.2, name="Follower camera")
text(s_fleet, 3.95, 1.3 + 3.2 * 9 / 16 + 0.05, 3.2, 0.5, ["Follower's front camera: box = leader, dashed line = image centre, "
     "arrow = offset. The boat on the right is the other follower."], size=10, color=MUTED)
steps = [("1", "Camera", "front camera, 1280x720, 10 frames/s"),
         ("2", "Detector + tracker", "leader's box (this project)"),
         ("3", "Box → commands", "offset → steering; box size vs. target size → throttle"),
         ("4", "Simulator", "commands sent back to the boat (Unity)")]
for i, (n, a, b) in enumerate(steps):
    yy = 1.3 + i * 0.68
    badge(s_fleet, 7.35, yy + 0.04, n, NAVY if n != "2" else LQ, d=0.36, size=12)
    text(s_fleet, 7.8, yy, 1.85, 0.66, [[(a, dict(bold=True, size=12))], [(b, dict(size=10, color=MUTED))]], space=0)
box(s_fleet, 3.95, 4.25, 5.65, 0.82, fill=BEST, name="Why it matters")
text(s_fleet, 4.1, 4.3, 5.4, 0.72, [[("Why it matters: ", dict(bold=True)), ("a missing or wrong box means wrong steering. "
     "In waves the camera pitches, the box jumps vertically, and the follower can lose the leader.", {})]],
     size=12, anchor=MSO_ANCHOR.MIDDLE)
notes(s_fleet, "Briefly, how the boat platform works. A leader boat drives a set route. Two followers keep formation behind it "
      "using their front cameras. Each frame, the detector and tracker give the leader's box. The horizontal offset of the box "
      "from the image centre sets the steering, and the box size compared with the target size sets the throttle, so the box "
      "is the follower's only sense of where the leader is. That is why detection and tracking accuracy matter, and why waves "
      "are hard: the camera pitches and the box jumps. In this project we evaluate the detector and tracker offline on "
      "frames recorded from these runs; we do not change the controller.")

# ================================================================ 5 Method overview
frame(s_method, "Method", "Two Comparisons on One Pipeline")
X0, Y0 = 0.4, 1.75
box(s_method, X0, Y0 + 0.55, 1.25, 0.9, name="Frame")
text(s_method, X0, Y0 + 0.6, 1.25, 0.8, [[("Camera", dict(bold=True))], [("frame", dict(bold=True))]], size=13, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space=0)
arrow(s_method, X0 + 1.3, Y0 + 1.0, X0 + 1.7, Y0 + 1.0)
text(s_method, X0 + 1.75, Y0 - 0.42, 2.9, 0.3, [[("DETECTOR", dict(bold=True, color=MUTED))]], size=10, spacing=150)
for i, (name, sub_t, col) in enumerate([("Traditional detector", "Fisher LDA scan + PCA + Gaussian Bayes", TRAD),
                                         ("YOLOv8s", "CNN trained by the drone team", YOLO)]):
    yy = Y0 + i * 1.1
    box(s_method, X0 + 1.75, yy, 2.9, 0.95, fill=WHITE, line=col, name=name)
    dot(s_method, X0 + 1.92, yy + 0.17, col, 0.16)
    text(s_method, X0 + 2.15, yy + 0.08, 2.45, 0.85, [[(name, dict(bold=True, size=14))], [(sub_t, dict(color=MUTED, size=11))]], space=2)
arrow(s_method, X0 + 4.7, Y0 + 1.0, X0 + 5.1, Y0 + 1.0)
text(s_method, X0 + 5.15, Y0 - 0.42, 3.0, 0.3, [[("TRACKER  ·  FLOW + KALMAN", dict(bold=True, color=MUTED))]], size=10, spacing=150)
for i, (name, sub_t, col) in enumerate([("None", "newest box as is", MUTED), ("Hand-tuned", "drone team's constants", HAND),
                                         ("MLE-learned Q", "fitted from training data", LQ)]):
    yy = Y0 + i * 0.72
    box(s_method, X0 + 5.15, yy, 2.55, 0.6, fill=WHITE, line=col, name=f"Tracker {name}")
    dot(s_method, X0 + 5.3, yy + 0.22, col, 0.16)
    text(s_method, X0 + 5.52, yy + 0.02, 2.15, 0.56, [[(name, dict(bold=True, size=13))], [(sub_t, dict(color=MUTED, size=10))]],
         anchor=MSO_ANCHOR.MIDDLE, space=0)
arrow(s_method, X0 + 7.75, Y0 + 1.0, X0 + 8.15, Y0 + 1.0)
box(s_method, X0 + 8.2, Y0 + 0.55, 1.0, 0.9, name="Output")
text(s_method, X0 + 8.2, Y0 + 0.6, 1.0, 0.8, [[("Target", dict(bold=True))], [("box", dict(bold=True))]], size=13, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, space=0)
for i, (lab, t, col) in enumerate([
        ("Comparison 1", "change the detector, keep the tracker: traditional vs. YOLOv8  (Q1)", TRAD),
        ("Comparison 2", "keep YOLOv8, change the tracker: hand-tuned vs. MLE-learned  (Q2)", LQ)]):
    yy = 4.2 + i * 0.48
    dot(s_method, 0.45, yy + 0.08, col, 0.2)
    text(s_method, 0.8, yy, 8.8, 0.4, [[(lab + ":  ", dict(bold=True)), (t, {})]], size=14)
notes(s_method, "Every pipeline has two parts. The detector finds the target in a frame; the tracker smooths the box and "
      "fills the frames between detections, using Lucas-Kanade optical flow and an 8-state Kalman filter. Comparison 1 "
      "swaps the detector. Comparison 2 keeps YOLOv8 and swaps how the tracker's constants are chosen: by hand, or by "
      "maximum likelihood from training data.")

# ================================================================ 6 Traditional detector
s5 = new_slide()
frame(s5, "Method  ·  Comparison 1", "A Detector Built Only From Course Methods")
steps = [("1", "Features", "Ch. 1", "Window resized to 24x17 px; grey level + gradient magnitude, each z-normalised: an 816-D vector x."),
         ("2", "Fisher LDA scan", "Ch. 3-2", "w = Sw⁻¹(m₁ − m₀), with shrinkage on Sw (816-D vs. few samples: Hughes). Score wᵀx at every position and 7 scales."),
         ("3", "Hard negatives", "Ch. 1", "Retrain on the false peaks of step 2: the design cycle of evaluate, then improve."),
         ("4", "PCA + Bayes", "Ch. 3-2, 3-1, 2", "Top 10 boxes → PCA to 30-D → one Gaussian per class, μ̂ and Σ̂ by MLE → P(target | x).")]
for i, (n, head, ch, body) in enumerate(steps):
    xx = 0.4 + i * 2.33
    box(s5, xx, 1.3, 2.13, 2.75, name=f"Step {n}")
    badge(s5, xx + 0.15, 1.45, n, TRAD)
    text(s5, xx + 0.65, 1.47, 1.45, 0.38, [[(ch, dict(color=MUTED))]], size=11, anchor=MSO_ANCHOR.MIDDLE)
    text(s5, xx + 0.12, 1.98, 1.92, 0.4, [[(head, dict(bold=True))]], size=15)
    text(s5, xx + 0.12, 2.4, 1.92, 1.6, [body], size=12)
    if i < 3:
        arrow(s5, xx + 2.15, 2.68, xx + 2.31, 2.68)
text(s5, 0.4, 4.25, 9.2, 0.9, [
    {"bullet": True, "runs": [("Output = box + posterior probability, used by the tracker exactly like YOLO's box + confidence.", {})]},
    {"bullet": True, "runs": [("Trained only on the training split. Drone: 40x11 window (drone boxes are wide); USV: 24x17. "
                               "No neural network anywhere.", {})]}], size=13, space=4)
notes(s5, "The traditional detector uses only course material. Step 1 turns any window into an 816-dimensional vector. "
      "Step 2 is Fisher's linear discriminant; because the score is linear we can evaluate it at every position and scale. "
      "With 816 dimensions and limited samples the within-class scatter is badly estimated, the Hughes effect, so we shrink "
      "it towards a diagonal. Step 3 retrains on its own mistakes. Step 4 re-scores the best 10 boxes with PCA and a "
      "two-class Gaussian Bayes classifier whose means and covariances are maximum-likelihood estimates. On held-out data "
      "this re-scoring separates true and false boxes well: AUC 0.96 on the boat data.")

# ================================================================ 7 YOLO + course methods
s6 = new_slide()
frame(s6, "Method  ·  Comparison 2", "YOLOv8 + Course Methods in the Tracker")
box(s6, 0.4, 1.3, 4.35, 3.8, name="Hand-tuned")
dot(s6, 0.6, 1.5, HAND, 0.2)
text(s6, 0.9, 1.42, 3.7, 0.4, [[("Drone team's tracker (hand-tuned)", dict(bold=True, size=15))]])
text(s6, 0.6, 1.95, 4.0, 3.1, [
    {"bullet": True, "runs": ["YOLOv8s → Lucas-Kanade optical flow → 8-state Kalman filter"]},
    {"bullet": True, "runs": ["Process noise Q: fixed diagonal, tuned by eye on drone video"]},
    {"bullet": True, "runs": ["Measurement noise R = 60·(0.5 / conf)²"]},
    {"bullet": True, "runs": ["Gate: accept a box within 1.5 box sizes"]},
    [("Tuned for a 30 fps camera. The boat camera runs at 10 Hz, so the box moves about 3x further per step.",
      dict(color=MUTED, size=12, italic=True))]], size=13, space=6)
box(s6, 4.95, 1.3, 4.65, 3.8, fill=WHITE, line=LQ, name="MLE Q")
dot(s6, 5.15, 1.5, LQ, 0.2)
text(s6, 5.45, 1.42, 4.05, 0.4, [[("Course method: learn Q by maximum likelihood", dict(bold=True, size=15))]])
text(s6, 5.15, 1.95, 4.3, 0.55, ["If the filter is right, each innovation ν = z − Hx̂ is Gaussian: ν ~ N(0, S(Q))  (Ch. 3-1)"], size=13)
box(s6, 5.15, 2.55, 4.25, 0.62, fill=CARD, name="Formula")
text(s6, 5.15, 2.55, 4.25, 0.62, [[("Q̂ = argmax_Q  Σₖ ln N(νₖ ; 0, Sₖ(Q))", dict(bold=True, size=17, font=HEAD))]],
     align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
text(s6, 5.15, 3.3, 4.3, 1.75, [
    "Sₖ = H Pₖ Hᵀ + R depends on Q through the filter, so we search Q × {0.3 … 1000} on training data only.",
    [("Also tried: MLE-learned R and a minimum-risk Bayes gate (Ch. 2). They helped on the drone and hurt on the boat.",
      dict(color=MUTED, size=12, italic=True))]], size=13, space=8)
notes(s6, "The drone team's tracker works on the drone video, but its noise settings were chosen by hand. We replace the "
      "process noise Q with a maximum-likelihood estimate. If the filter model is correct, the innovations are zero-mean "
      "Gaussian with covariance S, so we pick the Q that makes the observed innovations most likely, the Chapter 3 principle "
      "with the innovations as the samples. Q is always fitted on training data, never on the test sequences.")

# ================================================================ 8 Experimental setup
frame(s_setup, "Experiments", "Experimental Setup")
rows = [("", "Drone (real video)", "USV leader boat (simulator)"),
        ("Data", "3 videos, 1080p, 30 fps: testv4 (594 frames), IMG_7888 (932), Tello IMG_7923 (367; new drone, indoor)",
         "64 camera sequences, 1280x720, 10 Hz; 6 conditions: clear, rain, night, night+rain, dark storm, huge waves"),
        ("Ground truth", "Grounding DINO boxes fused and checked by eye (YOLO not used)", "Exact boxes from the simulator"),
        ("Train / test", "Train on one video, test on the other; Tello: train on both, test once",
         "Split by random seed: test seeds never seen in training"),
        ("Score", "Share of frames whose box overlaps the truth with IoU ≥ 0.5",
         "Same; detections reach the tracker 1 frame late (the real setup)")]
gt = s_setup.shapes.add_table(len(rows), 3, Inches(0.4), Inches(1.3), Inches(9.2), Inches(3.2))
gt.name = "Setup table"
tbl = gt.table
tblPr = tbl._tbl.tblPr
for k in ("bandRow", "firstRow"):
    tblPr.set(k, "0")
tbl.columns[0].width = Inches(1.5); tbl.columns[1].width = Inches(3.85); tbl.columns[2].width = Inches(3.85)
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c); cell.text = ""
        cell.fill.solid(); cell.fill.fore_color.rgb = NAVY if r == 0 else (CARD if r % 2 == 0 else WHITE)
        cell.margin_left = cell.margin_right = Inches(0.1); cell.margin_top = cell.margin_bottom = Inches(0.06)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]; run = p.add_run(); run.text = val
        run.font.name = BODY; run.font.size = Pt(12); run.font.bold = (r == 0 or c == 0)
        run.font.color.rgb = WHITE if r == 0 else INK
text(s_setup, 0.4, 4.65, 9.2, 0.5, [[("Statistics: ", dict(bold=True, color=INK)), ("Wilcoxon signed-rank test over sequences (USV); "
     "95% block-bootstrap interval over 1-second blocks (drone). Slow-computer case: detections 3 frames late.", {})]], size=12, color=MUTED)
notes(s_setup, "Two platforms. The drone data is real video; its ground truth comes from a different detector, Grounding DINO, "
      "so it is independent of YOLO, and we checked it by eye. The boat data is from our USV simulator, where the true box "
      "is exact. We always test on data not used for training: a different video for the drone, a different random seed "
      "for the boat. The score is the share of frames with IoU of at least 0.5.")

# ================================================================ 9 Result 1: drone
frame(s_result, "Result 1  ·  Detector", "Traditional Detector vs. YOLOv8: Drone")
cats = [n for _, n in VIDS]
bar_chart(s_result, 0.3, 1.2, 5.9, 3.55, cats, [("Traditional detector", [dc(v, 1, "only") for v, _ in VIDS], TRAD),
                                              ("YOLOv8", [dy(v, 1, "only") for v, _ in VIDS], YOLO)])
text(s_result, 0.45, 4.78, 5.7, 0.35, ["Detector alone, 1-frame delay. Share of frames with IoU ≥ 0.5."], size=11, color=MUTED)
picture(s_result, f"{MEDIA}/drone_testv4.png", 6.45, 1.3, w=3.15, name="Drone example")
chip(s_result, 6.45, 3.18, GREEN, "Ground truth", size=11, w=1.1)
chip(s_result, 7.65, 3.18, TRAD, "Traditional", size=11, w=1.0)
chip(s_result, 8.75, 3.18, YOLO, "YOLOv8", size=11, w=0.85)
text(s_result, 6.45, 3.6, 3.15, 1.5, ["Brick wall and paving tiles give the linear template many drone-like edges. "
     "On the new indoor Tello video it almost never finds the drone."], size=12)
notes(s_result, f"Comparison 1 on the drone. Tested cross-video, the traditional detector reaches {dc('testv4', 1, 'only'):.1f}% "
      f"and {dc('img7888', 1, 'only'):.1f}%, against {dy('testv4', 1, 'only'):.1f}% and {dy('img7888', 1, 'only'):.1f}% for YOLOv8. "
      "On the held-out Tello video, a different drone indoors, it finds almost nothing while YOLOv8 still gets a third of the "
      "frames. The picture is frame 100 of testv4: the traditional box sits on part of the drone and the wall behind it.")

# ================================================================ 10 Result 1: USV
s9 = new_slide()
frame(s9, "Result 1  ·  Detector", "Traditional Detector vs. YOLOv8: USV")
bar_chart(s9, 0.3, 1.2, 6.3, 3.55, [n for _, n in COND],
          [("Traditional detector", [usv[k]["classic|only"] for k, _ in COND], TRAD),
           ("YOLOv8", [usv[k]["yolo|only"] for k, _ in COND], YOLO)], label_size=10)
text(s9, 0.45, 4.78, 6.0, 0.35, ["Detector alone, 1-step delay, 64 test sequences."], size=11, color=MUTED)
stat(s9, 6.85, 1.3, f"{usv['all']['classic|only']:.0f}% vs {usv['all']['yolo|only']:.0f}%", "all conditions")
stat(s9, 6.85, 2.5, f"{usv['night']['classic|only']:.0f}% vs {usv['night']['yolo|only']:.0f}%", "at night: the template needs light")
stat(s9, 6.85, 3.7, "2 / 64", "sequences where the traditional pipeline beats YOLOv8 (p = 6×10⁻¹²)")
notes(s9, "On the boat the traditional detector is reasonable in clear water, 65 percent, and drops in rain. At night and in "
      "the dark storm it nearly disappears: the boat is almost black, so a template of grey level and edges has nothing to "
      "match. YOLOv8 hardly changes across conditions. Over all 64 sequences the traditional pipeline wins only 2. "
      "It is also slower: about 110 to 180 ms per frame on one CPU core, against about 11 ms for YOLOv8 on a GPU.")

# ================================================================ 11 Examples
s10 = new_slide()
frame(s10, "Result 1  ·  Detector", "What the Two Detectors Return")
for i, (f, cap) in enumerate([("usv_clear.png", "USV, clear: both boxes on the boat"),
                              ("usv_night.png", "USV, night: no traditional box; YOLOv8 still finds the boat"),
                              ("drone_img7888.png", "Drone, IMG_7888: no traditional box above threshold")]):
    xx = 0.4 + i * 3.1
    picture(s10, f"{MEDIA}/{f}", xx, 1.3, w=2.95, name=cap)
    text(s10, xx, 1.3 + 2.95 * 9 / 16 + 0.1, 2.95, 0.6, [cap], size=12)
chip(s10, 0.4, 3.85, GREEN, "Ground truth", size=12, w=1.3)
chip(s10, 1.95, 3.85, TRAD, "Traditional detector", size=12, w=1.8)
chip(s10, 4.0, 3.85, YOLO, "YOLOv8", size=12, w=1.0)
box(s10, 0.4, 4.3, 9.2, 0.75, fill=CARD, name="Takeaway")
text(s10, 0.6, 4.3, 8.8, 0.75, [[("Same thresholds, no tracker: the difference is the features. ", dict(bold=True)),
     ("Frames are taken at fixed positions (frame 350 of a test sequence; frame 200 of IMG_7888), not chosen for the result.",
      dict(color=MUTED))]], size=13, anchor=MSO_ANCHOR.MIDDLE)
notes(s10, "Three typical frames. In clear water both detectors find the boat. At night only YOLOv8 does. On the drone video "
      "the traditional detector's best box is below the confidence threshold, so it reports nothing.")

# ================================================================ 12 Result 2: drone
s11 = new_slide()
frame(s11, "Result 2  ·  Tracker", "YOLOv8 vs. YOLOv8 + MLE-Learned Q: Drone")
bar_chart(s11, 0.3, 1.2, 6.3, 3.55, cats, [("YOLOv8 only", [dy(v, 1, "only") for v, _ in VIDS], YOLO),
                                          ("+ hand-tuned tracker", [dy(v, 1, "hand") for v, _ in VIDS], HAND),
                                          ("+ MLE-learned Q", [dy(v, 1, "lq") for v, _ in VIDS], LQ)])
text(s11, 0.45, 4.78, 6.0, 0.35, ["1-frame delay (the real setup). Q learned on the other video(s)."], size=11, color=MUTED)
stat(s11, 6.85, 1.3, "+3 to +25", "points over the hand-tuned tracker in all 6 drone tests (1- and 3-frame delay)", color=LQ)
stat(s11, 6.85, 2.85, f"{dy('img7923', 1, 'lq'):.0f}% vs {dy('img7923', 1, 'only'):.0f}%",
     "held-out Tello video: learned Q vs. YOLOv8 alone (95% CI of the gain over hand-tuned: +9 to +43)")
notes(s11, "Comparison 2 on the drone. The tracker with the maximum-likelihood Q is best on all three test videos. With a "
      "3-frame delay, which imitates a slower onboard computer, the gain over the hand-tuned tracker is about 25 points on "
      "both training videos. On the held-out Tello video, a new drone and a new scene, the learned tracker reaches 70 "
      "percent against 33 for YOLOv8 alone.")

# ================================================================ 13 Result 2: USV
s12 = new_slide()
frame(s12, "Result 2  ·  Tracker", "YOLOv8 vs. YOLOv8 + MLE-Learned Q: USV")
bar_chart(s12, 0.3, 1.2, 6.3, 3.55, [n for _, n in COND],
          [("YOLOv8 only", [usv[k]["yolo|only"] for k, _ in COND], YOLO),
           ("+ hand-tuned tracker", [usv[k]["yolo|hand"] for k, _ in COND], HAND),
           ("+ MLE-learned Q", [usv[k]["yolo|learnedQ"] for k, _ in COND], LQ)], label_size=9)
text(s12, 0.45, 4.78, 6.0, 0.35, ["64 test sequences. MLE picks Q = 10x the drone value (10 Hz vs. 30 fps)."], size=11, color=MUTED)
stat(s12, 6.85, 1.25, "64 / 64", "sequences where learned Q beats hand-tuned (p = 4×10⁻¹²); 28 / 30 in extreme waves", color=LQ)
stat(s12, 6.85, 2.5, "4 of 6", "conditions where it is also higher than YOLOv8 alone; tie in huge waves")
stat(s12, 6.85, 3.75, f"{usv['dark_storm']['yolo|learnedQ']:.0f}% vs {usv['dark_storm']['yolo|only']:.0f}%",
     "dark storm: here YOLOv8 alone is better", color=TRAD)
notes(s12, "On the boat the hand-tuned tracker is worse than YOLOv8 alone everywhere: its constants were tuned for a 30 fps "
      "drone camera. Maximum likelihood finds a Q ten times larger, which matches the frame-rate ratio, and the learned "
      "tracker beats the hand-tuned one on all 64 sequences. Against YOLOv8 alone it is higher in clear, rain, night and "
      "night+rain, ties in huge waves, and loses in the dark storm, where detections are sparse and the camera pitches "
      "unpredictably, so a fresh detection beats a prediction.")

# ================================================================ 14 Result 3: scoreboard
s13 = new_slide()
frame(s13, "Result 3  ·  Both comparisons", "All Four Pipelines Side by Side")
avg2 = lambda f, arm: (f("testv4", 1, arm) + f("img7888", 1, arm)) / 2
darkc = lambda key: sum(usv[k][key] for k in ("night", "night_rain", "dark_storm")) / 3
pipes = [("Traditional detector", TRAD, usv["all"]["classic|only"], darkc("classic|only"), avg2(dc, "only"), dc("img7923", 1, "only")),
         ("Traditional + learned Q", TRAD, usv["all"]["classic|learnedQ"], darkc("classic|learnedQ"), avg2(dc, "lq"), dc("img7923", 1, "lq")),
         ("YOLOv8", YOLO, usv["all"]["yolo|only"], darkc("yolo|only"), avg2(dy, "only"), dy("img7923", 1, "only")),
         ("YOLOv8 + learned Q", LQ, usv["all"]["yolo|learnedQ"], darkc("yolo|learnedQ"), avg2(dy, "lq"), dy("img7923", 1, "lq"))]
hdr = ["Pipeline", "USV, all\n64 sequences", "USV, dark\nnight, night+rain, storm", "Drone\nmean of 2 videos", "Drone, held out\nTello video"]
gf = s13.shapes.add_table(5, 5, Inches(0.4), Inches(1.3), Inches(9.2), Inches(3.05)); gf.name = "Scoreboard"
t = gf.table
for k in ("bandRow", "firstRow"):
    t._tbl.tblPr.set(k, "0")
t.columns[0].width = Inches(2.8)
for c in range(1, 5):
    t.columns[c].width = Inches(1.6)
best = [max(range(4), key=lambda r: pipes[r][c + 2]) for c in range(4)]
for c, h in enumerate(hdr):
    cell = t.cell(0, c); cell.text = ""; cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    for j, line in enumerate(h.split("\n")):
        p = cell.text_frame.paragraphs[0] if j == 0 else cell.text_frame.add_paragraph()
        p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
        r = p.add_run(); r.text = line; r.font.name = BODY; r.font.size = Pt(13 if j == 0 else 10)
        r.font.bold = j == 0; r.font.color.rgb = WHITE if j == 0 else ICE
for r, (name, col, *vals) in enumerate(pipes, 1):
    cell = t.cell(r, 0); cell.text = ""; cell.fill.solid(); cell.fill.fore_color.rgb = WHITE
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = cell.text_frame.paragraphs[0]
    a = p.add_run(); a.text = "●  "; a.font.color.rgb = col; a.font.size = Pt(14); a.font.name = BODY
    b = p.add_run(); b.text = name; b.font.name = BODY; b.font.size = Pt(15); b.font.color.rgb = INK
    for c, v in enumerate(vals, 1):
        cell = t.cell(r, c); cell.text = ""; cell.fill.solid()
        cell.fill.fore_color.rgb = BEST if best[c - 1] == r - 1 else WHITE
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        rr = p.add_run(); rr.text = f"{v:.1f}%"; rr.font.name = BODY; rr.font.size = Pt(17)
        rr.font.bold = best[c - 1] == r - 1; rr.font.color.rgb = INK
text(s13, 0.4, 4.5, 9.2, 0.6, [[("Green = best in column. ", dict(bold=True, color=INK)),
     ("Share of frames with IoU ≥ 0.5, 1-frame delay. The detector decides most of the score. The learned tracker adds on top "
      "of YOLOv8 (not in the dark); on top of the traditional detector it helps only on the USV.", {})]], size=12, color=MUTED)
notes(s13, "This table puts both comparisons together. Changing the detector from traditional to YOLOv8 is worth 35 to 65 "
      "points. Changing the tracker from none to the MLE-learned one is worth a few points on the boat and up to 37 points on "
      "the held-out drone video when the detector is YOLOv8; the traditional detector gives too few correct drone boxes to follow. "
      "YOLOv8 with the learned tracker is the best or tied for best everywhere except the dark "
      "conditions on the boat, where YOLOv8 alone is best.")

# ================================================================ 15 Discussion
frame(s_disc, "Discussion", "What We Learned")
cols = [("Why the traditional detector loses", TRAD, [
            ("Light. ", "A fixed template of grey level and edges: USV 65% in clear water, 16% at night, 9% in the dark storm."),
            ("Clutter. ", "Brick and tiles look like drone edges; a new drone indoors: 0%."),
            ("Capacity. ", "One linear direction in 816-D from about 1-12 k boxes; YOLOv8 learns its features from far more data."),
            ("Speed. ", "110-180 ms per frame on one CPU core vs. about 11 ms for YOLOv8 on a GPU.")]),
        ("What course methods do add", LQ, [
            ("MLE beats hand-tuning ", "on both platforms: 64/64 USV sequences, +3 to +25 points on the drone."),
            ("It adapts to the detector: ", "on the USV, Q x10 for YOLOv8 and x30 for the noisier traditional detector."),
            ("Not a fix for a bad detector: ", "traditional + learned Q 31% → 35% on the USV; on the drone (13% correct boxes) it cannot help."),
            ("Limit: ", "with sparse detections (dark storm) prediction drifts; YOLOv8 alone wins.")])]
for i, (head, col, items) in enumerate(cols):
    xx = 0.4 + i * 4.7
    box(s_disc, xx, 1.3, 4.5, 3.3, name=head)
    dot(s_disc, xx + 0.2, 1.5, col, 0.22)
    text(s_disc, xx + 0.52, 1.42, 3.9, 0.4, [[(head, dict(bold=True, size=16))]])
    text(s_disc, xx + 0.2, 1.95, 4.15, 2.6, [{"bullet": True, "runs": [(a, dict(bold=True)), (b, {})]} for a, b in items],
         size=13, space=6)
box(s_disc, 0.4, 4.72, 9.2, 0.5, fill=NAVY, name="One line")
text(s_disc, 0.6, 4.72, 8.8, 0.5, [[("In one line: ", dict(bold=True, color=MINT)), ("the detector sets the ceiling; course methods "
     "decide how close the tracker gets to it.", dict(color=WHITE))]], size=14, anchor=MSO_ANCHOR.MIDDLE)
notes(s_disc, "Why does the traditional detector lose? Its features are fixed: grey level and edges. They fail when the light "
      "changes and when the background has the same kind of edges as the target. A single Fisher direction is a very small "
      "model for 816 dimensions; we needed shrinkage just to estimate the scatter matrix. But course methods are not "
      "useless: used for the decision and estimation parts around a learned detector, they replace hand-tuned constants "
      "with values learned from data, and that transfers across platforms.")

# ================================================================ 16 Conclusion (dark)
s15 = new_slide()
drop_nontitle(s15); dark(s15)
text(s15, 0.5, 0.35, 9.0, 0.3, [[("CONCLUSION", dict(bold=True, color=MINT))]], size=10, spacing=150)
style_title(s15.shapes.title, "Conclusion and Future Work", color=WHITE, box=(0.45, 0.6, 9.1, 0.62))
for i, (q, ans, col) in enumerate([
        ("Q1  Replace YOLOv8 with traditional PR?", "No. 31% vs. 73% on the USV, about 13% vs. 80% on the drone, and it fails in the dark.", TRAD),
        ("Q2  Improve YOLOv8 with traditional PR?", "Mostly yes. The MLE-learned tracker beats hand-tuning in every condition, and beats "
                                                    "YOLOv8 alone in all drone tests and 4 of 6 boat conditions.", LQ)]):
    yy = 1.45 + i * 1.45
    box(s15, 0.5, yy, 5.5, 1.3, fill=NAVY2, name=q)
    dot(s15, 0.7, yy + 0.22, col, 0.22)
    text(s15, 1.05, yy + 0.12, 4.85, 0.4, [[(q, dict(bold=True, size=15, color=WHITE))]])
    text(s15, 1.05, yy + 0.52, 4.85, 0.75, [ans], size=13, color=ICE)
text(s15, 0.5, 4.45, 5.5, 0.8, [[("Take-away: ", dict(bold=True, color=MINT)), ("use a learned detector to find the target, and course "
     "methods (MLE, Bayes) to set the tracker from data instead of by hand.", dict(color=WHITE))]], size=14)
text(s15, 6.4, 1.45, 3.2, 0.4, [[("Next steps", dict(bold=True, size=16, color=WHITE))]])
text(s15, 6.4, 1.95, 3.2, 3.2, [
    {"bullet": True, "runs": [("Weather classifier (LDA / Bayes) that picks a learned Q per condition, for the dark storm", dict(color=ICE))]},
    {"bullet": True, "runs": [("Bayes fusion of YOLOv8 confidence and the Fisher score", dict(color=ICE))]},
    {"bullet": True, "runs": [("Real boat footage; more drone videos", dict(color=ICE))]},
    {"bullet": True, "runs": [("Non-parametric densities (Parzen, k-NN) for the Bayes gate", dict(color=ICE))]}], size=13, space=9)
notes(s15, "To answer our two questions: traditional pattern recognition cannot replace YOLOv8 for detection here. But the "
      "same methods are valuable after the detector: learning the tracker's noise by maximum likelihood beats hand-tuned "
      "constants on both platforms and usually beats YOLOv8 alone. The open problem is the dark storm; a condition classifier "
      "that selects a Q learned for that condition is our next step.")

# ---------------------------------------------------------------- order, footers
order = [s_title, s_intro, s_rel, s_fleet, s_method, s5, s6, s_setup, s_result, s9, s10, s11, s12, s13, s_disc, s15]
for n, s in enumerate(order, 1):
    if s in (s_title, s15):
        continue
    text(s, 0.4, 5.28, 6.0, 0.25, [FOOTER], size=9, color=MUTED, name="Footer")
    text(s, 8.6, 5.28, 1.0, 0.25, [f"{n} / {len(order)}"], size=9, color=MUTED, align=PP_ALIGN.RIGHT, name="Slide number")
lst = prs.slides._sldIdLst
want = [s.slide_id for s in order]
els = {int(el.get("id")): el for el in lst}
for el in list(lst):
    lst.remove(el)
for i in want:
    lst.append(els[i])
prs.save(OUT)
print("saved", OUT, len(order), "slides")

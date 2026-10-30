#!/usr/bin/env python3
"""Evaluation-only prediction error during scheduled measurement censorship.

Censorship removes the selected box AFTER YOLO, so the raw detector output for
those frames is still logged. Matching raw boxes to the leader ID mask (ground
truth, never available to tracking/control) gives the measurement the tracker
would have received. Comparing it with the coasted estimate the controller
actually used measures forecast quality directly, separately from the closed-
loop formation outcome. Closed-loop images differ between arms after the first
divergence, so this is a per-arm forecast error, not a paired replay.
"""
import math
import numpy as np
from analyze import overlap, intended_gap

WIDTH = 1280


def leader_measurement(raw, id_boxes):
    """Return (offset, area) of the raw YOLO box best matching the leader ID box."""
    leader = [b for b in id_boxes if b['id'] == 1]
    if not leader or not raw:
        return None
    best = max(raw, key=lambda d: overlap(d[:4], leader[0]))
    if overlap(best[:4], leader[0]) <= 0.1:
        return None
    x0, y0, x1, y1 = best[:4]
    return ((x0+x1)/2-WIDTH/2)/(WIDTH/2), max(1.0, (x1-x0)*(y1-y0))


def gap_errors(rows, job):
    """Per-follower forecast errors on censored frames with a matched raw leader box."""
    out = dict(offset=[], log_area=[], frames=0, matched=0)
    if not job['gap']:
        return out
    for r in rows:
        if not intended_gap(r['t'], job) or r['t'] < 15:
            continue
        for side, key in [('Left', 'left_boxes'), ('Right', 'right_boxes')]:
            status = r['status'][side]
            out['frames'] += 1
            if not status['target_detected'] or status['target_area'] is None:
                continue  # track already expired: no forecast was used
            truth = leader_measurement(r['raw_detections'].get(side+'Front', []), r[key])
            if truth is None:
                continue
            out['matched'] += 1
            out['offset'].append(abs(status['target_center_offset']-truth[0]))
            out['log_area'].append(abs(math.log(max(status['target_area'], 1.0))-math.log(truth[1])))
    return out


def summarize(rows, job):
    e = gap_errors(rows, job)
    if not e['offset']:
        return dict(gap_frames=e['frames'], gap_matched_frames=0, gap_offset_mae=None,
                    gap_log_area_mae=None, gap_offset_p90=None)
    return dict(gap_frames=e['frames'], gap_matched_frames=e['matched'],
                gap_offset_mae=float(np.mean(e['offset'])), gap_offset_p90=float(np.percentile(e['offset'], 90)),
                gap_log_area_mae=float(np.mean(e['log_area'])))

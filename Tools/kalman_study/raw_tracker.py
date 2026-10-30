"""`raw` arm: NO filtering and NO prediction (ablation of all tracking filters).

State = the latest raw selected YOLO measurement; rates are zero, so the
controller gets no smoothed or predicted quantities. Combined with a zero hold
window (no coasting), a missing box means the track is lost on the next frame and
the unchanged lost-target fallback takes over. Same controller as `on_rs`; range
for that controller is c/sqrt(raw area) with zero rate. Label it exactly as
"no filter" — it is not production's non-Kalman behaviour (that is `off_short`).
"""
import math
from robust_tracker import RobustTracker


class RawTracker(RobustTracker):
    def __init__(self, kalman=False, tuning=None):
        super().__init__(kalman=False, tuning=tuning)

    def observe(self, offset, area, now, confidence=1.0):
        if self.x is None:
            self.initialize(offset, area, now)
            return
        self.predict_to(now)
        self.x[0] = [float(offset), 0.0]
        self.x[1] = [math.log(max(float(area), 1.0)), 0.0]
        self.last_seen = float(now)
        self.last_z = self.x[:, 0].copy()
        self._bounds()

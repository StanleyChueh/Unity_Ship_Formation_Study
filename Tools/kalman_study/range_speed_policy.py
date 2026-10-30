"""d04 shared longitudinal law (both `on_rs` and `off_rs`; only the estimator differs).

The original controller converts box AREA error to throttle and leads leader
speed only on acceleration ("slowing down is handled by the area loop"), with a
0.9 throttle ceiling (~21 m/s) against a leader cruising up to 20 m/s. e01
catastrophes were followers falling behind with no catch-up margin, or
overshooting a decelerating leader. This law commands SPEED from the estimated
range and range rate (published by rs_hooks), using the leader-speed telemetry
the controller already receives:

    v_cmd = v_leader + clamp(KP*(r_hat - R_REF) + KD*rdot_hat, DV_MIN, DV_MAX)
    throttle = v_cmd * LEADER_SPEED_THROTTLE_FF   (plant ~23.3 m/s per unit)

with a too-close brake. Steering, lost-track fallback and all else unchanged.
The peer-follower rescue throttle cap is skipped while this law is active.
"""

CONSTANTS = '''
# ---- d04 shared range/speed law (Tools/kalman_study/range_speed_policy.py) ----
RS_RANGE_REF = 25.6
RS_KP = 0.6
RS_KD = 0.5
RS_DV_MIN = -8.0
RS_DV_MAX = 4.0
RS_MAX_THROTTLE = 1.0
RS_MIN_CONF = 0.10
RS_TOO_CLOSE_M = 14.0
RS_TOO_CLOSE_DV = 3.0
'''

LAW = '''
        # d04 shared range/speed law: speed command from the estimator's range.
        _rs = front_state.get("range_estimate")
        if _rs is not None and front_visual_ref_ready and front_prediction_confidence >= RS_MIN_CONF:
            _r_hat, _r_dot = float(_rs[0]), float(_rs[1])
            _dv = clamp(RS_KP * (_r_hat - RS_RANGE_REF) + RS_KD * _r_dot, RS_DV_MIN, RS_DV_MAX)
            if _r_hat < RS_TOO_CLOSE_M:
                _dv = min(_dv, -RS_TOO_CLOSE_DV)
            throttle = clamp((float(state.get("leader_speed", 0.0)) + _dv) * float(LEADER_SPEED_THROTTLE_FF), 0.0, RS_MAX_THROTTLE)
            throttle_ceiling = max(throttle_ceiling, RS_MAX_THROTTLE)
            _kf_approach_ratio = 0.0
            _rs_active = True
'''


def patch_control(text):
    anchors = [
        ('            throttle = max(0.0, throttle - kf_d)\n', '            throttle = max(0.0, throttle - kf_d)\n'+LAW),
        ('    throttle = 1.0\n', '    throttle = 1.0\n    _rs_active = False\n'),
        ('    if not front_detected or front_stale:\n        peer_steer_bias, peer_throttle_bias = compute_peer_rescue_bias(',
         '    if (not front_detected or front_stale) and not _rs_active:\n        peer_steer_bias, peer_throttle_bias = compute_peer_rescue_bias('),
    ]
    for old, new in anchors:
        assert text.count(old) == 1, ('range/speed anchor changed', old)
        text = text.replace(old, new)
    text += CONSTANTS
    compile(text, 'range-speed-control.py', 'exec')
    return text

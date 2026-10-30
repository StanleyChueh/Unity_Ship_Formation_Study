"""Proposed shared short-loss policy for a NEW tagged development batch only.

Not imported by d01 or production. Both KF and EMA receive the same age-based
confidence, so this policy cannot manufacture a Kalman-only advantage.
"""


def patch_control(text):
    old='''        if front_stale:
            steer *= STALE_TARGET_STEER_SCALE
            if throttle > 0.0:
                throttle = max(throttle * STALE_TARGET_THROTTLE_SCALE, SEARCH_FORWARD_THROTTLE)'''
    new='''        if front_stale:
            # Shared short-loss policy: avoid an immediate speed drop while a
            # recent track remains credible; return to conservative attenuation
            # as the common age-based confidence approaches the 3s expiry.
            coast_weight = clamp((front_prediction_confidence - 0.10) / 0.60, 0.0, 1.0)
            coast_steer_scale = STALE_TARGET_STEER_SCALE + (1.0 - STALE_TARGET_STEER_SCALE) * coast_weight
            coast_throttle_scale = STALE_TARGET_THROTTLE_SCALE + (1.0 - STALE_TARGET_THROTTLE_SCALE) * coast_weight
            steer *= coast_steer_scale
            if throttle > 0.0:
                throttle = max(throttle * coast_throttle_scale, SEARCH_FORWARD_THROTTLE)'''
    assert text.count(old)==1,'Shared policy anchor changed'
    result=text.replace(old,new)
    compile(result,'shared-coast-control.py','exec')
    return result

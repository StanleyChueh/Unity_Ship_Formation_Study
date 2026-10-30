"""Vision adapter shared by robust KF ON and matched EMA OFF experiments."""
from robust_tracker import RobustTracker
from usv.state import runtime_settings


def enabled():
    return bool(runtime_settings.get('enable_kalman_filter', True))


def publish(state, tracker, now):
    offset, velocity, area, area_velocity = tracker.state()
    state.update(track_offset_velocity=velocity, track_area_velocity=area_velocity,
                 track_vertical_velocity=0.0, predicted_offset=max(-1.,min(1.,offset+velocity*.03)),
                 predicted_area=max(1.,area+area_velocity*.03), prediction_confidence=tracker.confidence(now),
                 kf_coast_time=now, kf_rejected=False)
    state['kf'] = tracker if tracker.kalman else None


def update(state, center_offset, center_y_norm, area, current_time,
           ego_speed_mps=0., ego_yaw_rate_dps=0., det_conf=1.):
    tracker = state.get('_robust_tracker')
    if tracker is None or tracker.kalman != enabled() or current_time-tracker.last_seen>3.00001:
        tracker = RobustTracker(kalman=enabled())
        state['_robust_tracker'] = tracker
    tracker.observe(center_offset, area, current_time, det_conf)
    publish(state, tracker, current_time)
    state.update(track_prev_measurement_time=current_time, track_prev_center_offset=center_offset,
                 track_prev_center_y=center_y_norm, track_prev_area=area)


def coast(state, current_time):
    tracker=state.get('_robust_tracker')
    if tracker is None:return
    if tracker.kalman != enabled():
        # A GUI toggle during a blackout changes mode immediately, without
        # inventing a new observation or extending the track's lifetime.
        previous=tracker
        offset,velocity,area,area_velocity=previous.state()
        tracker=RobustTracker(kalman=enabled())
        tracker.initialize(offset,area,previous.time)
        tracker.x[:,1]=[velocity,area_velocity/area]
        tracker.P=previous.P.copy()
        tracker.noise_var=previous.noise_var.copy()
        tracker.last_seen=previous.last_seen
        tracker._ema=tracker.x[:,0].copy()
        state['_robust_tracker']=tracker
    tracker.predict_to(current_time,missing=True)
    publish(state,tracker,current_time)
    offset,_,area,_=tracker.state()
    state.update(target_center_offset=max(-1.,min(1.,offset)),target_area=area)


def posterior(state, offset, area):
    tracker=state.get('_robust_tracker')
    if tracker is None:return offset,area
    offset,_,area,_=tracker.state()
    return max(-1.,min(1.,offset)),area

#!/usr/bin/env python3
"""Change waves in the running Unity Editor scene WITHOUT editing config.py.

Sends the same 'set_wave' UDP command usv_controller.py sends at startup to the
Editor's WaveController (port 5070). Study simulators listen on remapped ports
(47600+), so this cannot affect a running study batch.

  python3 Tools/kalman_study/set_wave_live.py --large 3.0     # huge swell (study C1/C10)
  python3 Tools/kalman_study/set_wave_live.py --large 0.55    # back to the default
Send it after the formation has locked (the app re-sends config values at startup).
"""
import argparse
import json
import socket

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--large', type=float, default=0.55, help='large swell height (m): 0.55 default, 1.0-1.5 rough, 3.0 huge')
p.add_argument('--scale', type=float, default=0.040, help='large-wave spatial frequency (higher = shorter, steeper waves)')
p.add_argument('--ripple', type=float, default=0.50, help='visual ripple height (>0.65 causes YOLO glitter)')
p.add_argument('--turbulence', type=float, default=0.12)
a = p.parse_args()
cmd = dict(cmd='set_wave', wave_height=a.ripple, turbulence=a.turbulence, large_wave_height=a.large,
           large_wave_scale=a.scale, wave_scale=0.45, flow_speed=0.010, camera_tilt_strength=0.50)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.sendto(json.dumps(cmd).encode(), ('127.0.0.1', 5070))
print('sent', cmd)

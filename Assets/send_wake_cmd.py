"""Live-tune the leader's stern wake without restarting usv_controller.py.

Unity's WaveController listens on WAVE_CONTROL_PORT (5070) and applies the
settings immediately, so you can sweep the occlusion level while a run is in
progress and watch the `[Metrics] leader=` percentage react.

    python send_wake_cmd.py 0.35       # intensity 0.0 (baseline) .. 1.0 (max)
    python send_wake_cmd.py 0.5 all    # apply to every boat, not just the leader
    python send_wake_cmd.py off        # no wake at all (control run)

Sweep procedure: start at 0.2 and step up by 0.1, giving each step ~30 s.
Record the leader detection rate at each step; the band worth reporting is
roughly 40-70%.  Stop stepping when it collapses toward 0%.
"""
import json
import socket
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from usv.config import wake_params  # noqa: E402

PORT = 5070

arg = sys.argv[1] if len(sys.argv) > 1 else "0.35"
target = sys.argv[2] if len(sys.argv) > 2 else "leader"

if arg.lower() == "off":
    cmd = {"cmd": "set_wake", "enable": 0, "target": target}
    label = "off"
else:
    try:
        intensity = float(arg)
    except ValueError:
        sys.exit(f"expected an intensity 0.0-1.0 or 'off', got '{arg}'")
    cmd = {
        "cmd": "set_wake",
        "enable": 1,
        "target": target,
        **wake_params(intensity),
    }
    label = f"intensity={intensity:.2f}"

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(json.dumps(cmd).encode("utf-8"), ("127.0.0.1", PORT))
s.close()
print(f"sent wake {label} → target={target} port={PORT}")
if "alpha" in cmd:
    print(
        f"  rate={cmd['rate_over_time']:.0f}/s +{cmd['rate_over_distance']:.0f}/m "
        f"life={cmd['lifetime']:.1f}s alpha={cmd['alpha']:.3f} "
        f"puff={cmd['start_size_max'] * cmd['size_growth']:.1f}u max={cmd['max_particles']}"
    )

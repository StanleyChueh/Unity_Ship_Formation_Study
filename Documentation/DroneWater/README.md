# Drone-view water and wake revision

The repeated foam texture was especially conspicuous from the overhead camera.
It has been replaced by procedural value noise at several scales, with domain
warping and pixel-footprint filtering. Foam detail is aligned with persistent
distance along each boat's recorded path and signed distance across that path.
Each boat has a different initial pattern offset. Old foam separates into
spreading streaks and fades instead of remaining a filled triangular carpet.
Filtering suppresses aliasing both at distance and where overlapping wakes
switch between different track coordinates.

The wake field now uses ARGBHalf: red is the unchanged physical wake height,
green is foam coverage, blue/alpha are foam coordinates. Those extra channels
change appearance only. CPU and GPU wave-height formulas are unchanged.

Ocean normals now combine the shared physical swell/wake slopes with fine
world-space ripple detail. Lighting uses the analytic world normal directly,
so broad wave faces remain visible from overhead without depending on the
water mesh's tangent seams. This replaces the nearly uniform overhead color;
it does not add random camera shake or increase wave displacement.

Settings remain physical wake strength 1.0 and foam strength 1.5. The isolated
captures cover straight running (360 m circle radius) and tighter turns (110 m
radius), at 18 m/s cruise. `straight-overhead.png`, `turn-overhead.png`, and
`turning-wakes.mp4` show the revised aerial appearance. Onboard views are also
included. The test drone camera follows the leader and rotates with its heading.

Unity builds and CPU/GPU height checks passed. See `checks.json` and the detailed
check logs. The capture harness is the existing isolated rig, extended with an
orthographic overhead view. The actual formation-controller check is recorded
separately in `vision-summary.json` and `vision-checks.txt`.

This remains an approximate procedural water/foam material, rather than a
photorealistic fluid simulation or an exact match to the supplied video still.

The final actual-controller run tracked for 33.439 seconds: both
followers had 100% leader detection, 0% stale tracks, and no near misses.
Restart Unity Play mode and the Python controller to load the revised wake
render target and shader state.

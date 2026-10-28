# Ocean surface and camera coupling

`USVOceanSurface` supplies one world-space swell field to the water shader and
Suimono's height queries. Rendering and physics use the same four wave vectors,
amplitudes and phases. The shader displaces the water mesh and uses analytic
slopes for lighting. The matching CPU height queries drive buoyancy and
HullWaveResponse. The stern-wave field is added to both paths as before.

Cameras mounted on a boat inherit its physical translation and rotation.
CameraWaveTilt skips its independent tilt when a mounted camera's hull already
has HullWaveResponse. Hull damping increased from 0.3 to 0.8 to reduce excessive
resonance. There is no added random camera shake. Steering, acceleration, and
ordinary hull inertia still contribute to motion.

Fine normal-map ripples remain visual detail; their shading is reduced relative
to the actual swells. Refraction and foam height masks use the shared swell
height rather than the old unrelated texture-height pattern.

## Settings

In `Assets/usv/config.py`:

```python
WAVE_CONTROL_ENABLE = True
SUIMONO_LARGE_WAVE_HEIGHT = 0.55
SUIMONO_LARGE_WAVE_SCALE = 0.040
```

Height now explicitly means a swell height budget in metres: the sum of the
component peak-to-trough heights. Actual local wave heights are usually smaller
because the components do not all peak together. It is not a calibrated
significant-wave-height or Beaufort measurement.

- `0.0`: flat ambient water.
- `0.55`: current gentle default.
- `2.0`: large-wave verification setting.

Increasing height changes both visible swells and hull/camera motion. Increasing
scale shortens wavelengths; reducing scale lengthens them. Parameters transition
smoothly over about 1.5 seconds. The hull responds to local slopes and changes
in surface height with inertia, so it does not instantly copy each wave or
shake simply because a large wave exists elsewhere.

`SUIMONO_CAMERA_TILT_STRENGTH` is a legacy setting for cameras without hull-driven
motion; it does not amplify the mounted follower cameras. Stern-wave strength
remains `WAKE_REALISTIC_STRENGTH`.

## Verification

The calm, moderate and rough runs use the same trajectory and hull driver, with
stern waves disabled. The right follower's motion is measured after the initial
12 seconds. See `metrics.json`, the three motion CSVs, and `*-checks.txt`.

| Ambient height budget | Hull pitch range | Hull roll range | Camera tilt variation (standard deviation) |
|---|---|---|---|
| 0 m | 2.47° to 3.00° | -0.34° to 0.03° | 0.068° |
| 0.55 m | 1.05° to 5.29° | -3.26° to 4.19° | 2.937° |
| 2.0 m | -4.03° to 11.09° | -11.81° to 15.18° | 7.494° |

The steady positive pitch in calm water is running trim, not wave shaking.
The CSV's legacy `camera_roll_deg` column records signed 3D camera tilt relative
to world up, including pitch; it is not a pure roll Euler angle.

At six times per run, a diagnostic shader sampled the same shared include used
by the water shader. Its heights and slopes were checked against the CPU formula
at 4,096 positions. Maximum observed absolute error was below 0.00004 m for
height (and below 0.00004 for dimensionless slopes).

`waves-and-camera.mp4` shows external water above the mounted-camera view,
with calm water on the left and rough water on the right.
`calm-vs-rough-camera.mp4` shows the same mounted camera in the two sea states.
The images include external water-level and onboard views. These are approximate
linear swells; this change does not implement breaking-wave fluid simulation.

The capture harness sources are retained under `Harness`, outside Assets. For
an isolated project copy, put USVCaptureRig in Assets, USVCaptureBuild in
Assets/Editor, and USVOceanProbe.shader in Assets/Resources beside the shared
USVOceanSurface.cginc. Build using USVCaptureBuild.Build, then launch with
`-usvcapture <output> -usvsea 0 -usvnowake -usvvideo`, repeating with sea 0.55 and
2.0. The harness uses private ports. In `-usvvision` mode, CPU/GPU readback
validation is skipped to avoid interrupting the live camera streams; the
separate surface tests perform those checks.

## Formation-controller integration

The final Unity build and standalone C# compile check passed without errors.
The actual YOLO controller ran on isolated ports for 33.179 tracked seconds
with default 0.55 m swells and stern wakes enabled. Both followers recorded
100% leader detection and 0% stale tracks, with no near misses.
Formation IoU averaged 0.861; per-boat formation RMS averaged
1.70 m. This is a short integration check, not a guarantee
for every sea state. The full summary and snapshots are included.

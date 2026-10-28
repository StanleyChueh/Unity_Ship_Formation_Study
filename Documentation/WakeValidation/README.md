# Water and stern-wake verification — 2026-10-28

The ambient-ocean implementation and calm/rough camera tests have since been
updated. See [Ocean coupling](../OceanCoupling/README.md) for the current design.

The wake now displaces the water surface, changes its reflection normals, and
feeds the same height calculation into buoyancy. HullWaveResponse samples the
water beneath the bow, stern and sides to drive pitch and roll; the cameras
inherit the hull motion. Ambient Suimono waves remain enabled by the Python
moderate-sea preset.

The inherited Kelvin calculation had the wrong sign in its wave phase. This
was corrected in both CPU and GPU implementations. A finite-width transom
shoulder crest and adjacent trough supplement the far-field Kelvin pattern.
This close-hull shape is an approximation, not a CFD hull simulation.

Wake shading now samples the height field per pixel, preserving crests that
were blurred by the ocean mesh. The wake texture shares Suimono's normal-map
sampler to fit the GPU sampler limit. Foam is broken into patches and uses a
neutral daylight response instead of the former beige strip. Repeated wake
commands preserve the recorded tracks.

## Review

- `before.png`: inherited unfinished render.
- `wake.png`, `water-level.png`: final normal-strength render.
- `wake-motion.mp4`: normal-strength chase view.
- `boat-camera.mp4`: normal-strength camera mounted on the right follower.
- `vision-camera.png`: right follower camera during the actual YOLO controller run.

Videos contain 88 frames at 10 fps, sampled over approximately 10 simulation
seconds. They are from the isolated formation-driver run. The production
vision controller was verified separately; its measurements are included.
The 3x diagnostic amplitude is used only in the stress test; the project
configuration stays at strength 1.0.

## Checks

Unity 2022.3.62f3 Linux player build: zero C# or shader errors. Both normal and
3x stress players exited normally with no runtime exceptions or validation
errors.

At six normal-run times, 8,281 GPU texel-centre samples were compared against
the CPU wake formula. Maximum error was 0.000231 m. Normal wake-field extrema
were approximately 0.41–0.46 m (absolute displacement, not peak-to-trough height).
Repeated wake-setting commands preserved the existing CPU field.

Normal-run hull motion during seconds 8–33:

| Hull | Pitch | Roll | Vertical position span |
|---|---:|---:|---:|
| Leader | −3.8° to +8.9° | −7.7° to +3.8° | 0.64 m |
| Left follower | −1.5° to +6.8° | −3.3° to +2.9° | 1.46 m |
| Right follower | −4.0° to +7.2° | −5.4° to +4.1° | 1.77 m |

The followers are normally outside the leader's wake at their lateral offsets;
their motion there comes from the ambient sea. In the 3x stress run, the right
follower was steered across the leader's track. It encountered wake displacement
of −0.286 to +0.595 m and roll of −23.1° to +26.3°, and stayed upright. This is
a response stress test, not the default sea setting.

The actual production YOLO controller was then run headlessly on private ports
against the same player for 33.664 tracked seconds. Both followers recorded
100% leader detection, 0% stale tracks, and no near misses. Formation IoU
averaged 0.742; per-boat formation RMS averaged 3.70 m. This short run establishes
that tracking still operates with the changed water; it does not establish
long-run performance for every trajectory or sea state.

See `checks.txt`, `vision-summary.json`, `vision-snapshots.csv`, and the three
`motion-*.csv` files for measurements. The summary's `mean_distance` values are
the controller's visual proxy; use its formation geometry metrics for metres.

## Capture harness

`Harness/USVCaptureRig.cs` and `Harness/USVCaptureBuild.cs` are verification-only
sources, outside Assets. To reproduce the isolated driver test, copy Assets,
Packages and ProjectSettings into a temporary project. Add the rig to its
Assets folder and the build entry point to Assets/Editor. Build with:

```bash
USV_BUILD_OUT=/tmp/usv-verification/usv.x86_64 /path/to/Unity \
  -batchmode -projectPath /tmp/project-copy -buildTarget Linux64 \
  -executeMethod USVCaptureBuild.Build -logFile /tmp/usv-build.log
```

Check the log for C# and shader errors even when Unity reports a successful
build. Run the player with `-usvcapture /tmp/captures -usvwakegain 1`.
`-usvvideo` adds sequential boat/chase frames, and `-usvcrosswake` makes the right
follower cross the wake. The rig uses private ports and disables camera streaming
unless `-usvvision` is supplied. Vision mode also disables the rig's substitute
driver: configure the copied Python controller for its private ports before
importing `usv` (the package imports app immediately). Ports are UDP left RX/TX
46110/46100, right RX/TX 46111/46101, leader 46102, wave 46103; camera TCP ports
are the project defaults plus 35000. Replace the copied app's legacy 5065
fallback with 46100. Keep all of these verification overrides out of the live
project configuration.

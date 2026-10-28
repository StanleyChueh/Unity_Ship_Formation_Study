# Heavier stern wake and daylight review

This supersedes the earlier RealismReview candidate. The PNGs and videos here
are captured from Unity. They are not generated pictures of the finished scene.
The scene remains visibly simulated; photorealism has not been established.

## Changes

- Raised physical wake strength to 1.15 and independent foam strength to 2.0.
  Fresh transom wash has connected, uneven white water; older foam separates
  into broken streaks instead of a pattern of holes along the entire wake.
- Increased spray from 90 to 140 particles per metre, widened the droplet
  clusters, and raised maximum vertical launch speed from 0.28 to 0.32 times
  boat speed. Droplets fall under gravity and disappear at the water surface.
  Removed the experimental connected spray meshes, which looked like wires.
- Added a reversible daytime lighting preset: sun elevation 38 degrees,
  azimuth 145 degrees, intensity 1.15, neutral sky, ambient fill and light haze.
  The sun starts behind the follower cameras to reduce glare in their view.
- Corrected the shared ocean's reflection blend and specular normalization.
  Filtered unresolved surface slopes near the horizon to reduce striped
  reflections. Nearby geometry and hull response still use the shared waves.
- Kept camera motion driven by hull buoyancy and wave attitude. The lighting
  and foam controls do not add independent camera shake.

## Controls

In `Assets/usv/config.py`:

```python
WAKE_REALISTIC_STRENGTH = 1.15
WAKE_REALISTIC_FOAM_STRENGTH = 2.0
WAKE_REALISTIC_SPRAY = True
```

The first setting changes physical wake displacement and spray together. Foam
strength changes white-water coverage independently. Spray density and launch
speed are fields on BoatSternWake. Raising displacement aggressively also makes
tracking harder, so it should not be used solely to whiten the wake.

WaveController's `useDaylightPresentation` enables the preset at Play startup.
The runtime USVDaylightPresentation component exposes the sun settings. Restart
Play after changing the preset so its sky reflection is captured again. Disable
the component to restore the prior lighting and water material settings.

Restart Unity Play mode and the Python controller to load all changes.

## Validation and limits

See `checks.json`, `straight-checks.txt`, `turn-checks.txt` and the production
controller's `vision-summary.json` / `vision-checks.txt` for the final run data.
Straight and turning capture runs use a controlled trajectory. The separate
production run uses the actual Python vision controller over private ports.
That short regression check does not establish long-duration tracking quality.

The final Linux build reported no C# or shader errors. Both capture runs
completed without runtime exceptions. Maximum CPU/GPU wake disagreement was
0.000243 m; the shared swell height/slope check stayed below 0.0000074.
Sampled spray rose as high as 1.855 m above the water. Hiding particle spray
at the same frame changed 4,505 / 7,383 onboard pixels (straight / turn,
RGB difference greater than 5), confirming visibility in that camera.

The production controller ran for 33.7 seconds. Mean per-boat formation RMS
error was 3.98 m and mean formation IoU was 0.787. The leader track remained
available throughout, including coasting over missed detections: stale frames
were 10.1% left and 4.1% right. These should not be reported as 100% fresh
detections. Earlier, stronger wake/glare trials lost formation and were rejected.

Review `comparison.mp4` for the earlier candidate alongside this version, or
`follower-camera.mp4` for the new onboard clip alone. Those videos use controlled
trajectories from separate runs. `production-follower.png` and
`production-overhead.png` come from the actual vision-controller run.

The daylight preset uses a consistent sky cubemap for all cameras. It currently
does not add local boat reflections. Foam still uses a procedural coverage field;
boat materials and the sparse environment also limit realism. These changes
should not be described as indistinguishable from real camera footage.

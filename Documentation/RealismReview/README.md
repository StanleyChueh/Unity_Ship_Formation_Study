# Water/spray review candidate

Historical candidate: see [HeavyWakeDaylight](../HeavyWakeDaylight/README.md)
for the newer wake, particle-only spray and daylight settings.

**Status: improved implementation, but the requested “indistinguishable from real
footage” quality bar is not met.** These are raw Unity captures, not generated
images of a finished scene. Technical checks below establish correctness and
integration, not photorealism.

Changes:

- Replaced the four dominant sine components with sixteen wavelengths,
  directions and phases. Component energy is normalized to preserve the prior
  approximate displacement RMS: 0.20 times the configured height scale. The
  parameter is now a nominal scale, not a bound on summed crest heights.
- Shared the new spectrum and its analytic slopes between rendering and CPU
  buoyancy. Fine, filtered directional ripples replace the previous procedural
  bump pattern. The over-emphasized face-lighting was reduced.
- Used a new shader-array property name to avoid an older four-element binding
  surviving in the editor.
- Removed track-coordinate encoding from the wake render target. It caused
  close-view precision/stretching artifacts. The field is back to RGHalf;
  non-repeating world-space detail supplies foam texture.
- Added water-surface clipping to spray so fallen particles do not show through
  the ocean. Increased droplet density/size and added short, uneven rising
  spray sheets that break into particles instead of complete fountain arches.
- Added a generated photographic droplet texture for spray and fine foam detail.
  See image-generation.txt for the exact prompt, tool mode, and saved asset.

Review files:

- drone-comparison.mp4: previous aerial implementation versus this candidate,
  from separate runs of the same turning test.
- follower-camera.mp4: unaltered onboard capture sequence from this candidate.
- straight/turn-close.png and straight/turn-follower.png: camera snapshots.
- straight/turn-without-spray.png: same-frame control captures with particle and
  spray-sheet renderers hidden.

What still needs work:

The close-view foam still has a procedural surface appearance, and the connected
spray sheets can read as rendered strands. The existing boat materials, lighting,
reflections and environment also remain visibly synthetic. This implementation
should not be represented as a photorealistic reconstruction of the references.

Verification:

The Unity Linux build has zero C# or shader errors. Straight and turning captures
completed without runtime exceptions or CPU/GPU validation failures. The shared
swell height/slope check compares 4,096 GPU points against CPU evaluation per
capture; wake validation also runs independently. checks.json contains errors,
observed particle heights and the number of pixels changed by hiding spray at
the same frame. The same-frame comparison checks actual camera visibility;
particle count alone was not accepted as proof that spray was visible.

The production controller run is recorded in vision-summary.json and
vision-checks.txt. That is a short regression check, not evidence of visual
realism. The tests use private network ports and a separate project copy.

Restart Unity Play mode and the Python controller to load the new spectrum,
particle materials and spray-sheet component. Defaults remain wake strength 1.0,
foam strength 1.5, ambient nominal height 0.55 m. No independent camera shake was
added.

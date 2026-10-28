# Wake white-water revision — 2026-10-28

The supplied reference shows dense aerated water and low spray, rather than
simply high waves. The previous wash was too narrow and sparse. Its appearance
barely changed when the physical wave-height multiplier was raised to 3.5.

Changes:

- Broader wash with a filled turbulent core, slower spreading, and approximately
  three seconds of decay at cruise speed.
- Higher foam coverage, with fine moving texture variation to avoid a uniformly
  white surface.
- Denser, smaller spray clusters, biased toward broad, low chine sheets rather
  than a tall central plume.
- Independent foam coverage control, carried from Python to Unity over UDP.

Current settings in Assets/usv/config.py:

```python
WAKE_REALISTIC_STRENGTH = 1.0
WAKE_REALISTIC_FOAM_STRENGTH = 1.5
WAKE_REALISTIC_SPRAY = True
```

The user's previous wave strength of 3.5 was lowered to 1.0 because the close
render showed tall wall-like ridges. Foam strength was set to 1.5 to obtain the
fuller wash without increasing physical wave displacement. Increase foam
strength to 2.0 for still greater coverage. Wave strength continues to affect
wave displacement and spray. Foam strength affects surface coverage only.
Restart the Python controller to send changed settings.

The wave-height formulas and ocean/camera coupling are unchanged. This revision
changes white-water appearance; the physical amplitude reduction is a settings
change. Missing foam_strength in older UDP messages defaults to 1.0.

`tuned-close.png` and `tuned-follower.png` show the current settings during the
actual production vision-controller run. `normal-*` uses physical strength 1
and foam strength 1; `excess-height-*` demonstrates why physical strength 3.5
is a poor substitute for more foam.

Unity player build: zero C# or shader errors. Normal and 3.5-strength captures
finished without runtime exceptions or CPU/GPU validation failures. The actual
YOLO controller ran on isolated ports for approximately 33.5 tracked seconds
with wave strength 1 and foam strength 1.5; both followers recorded 100% leader
detection, zero stale tracks, and no near misses. See the included summaries.

The result remains a stylized surface-foam and particle approximation. It is
not a photorealistic match to the reference or a validated turbulent-fluid
simulation.

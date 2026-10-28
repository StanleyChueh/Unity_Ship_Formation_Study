# Automatically labeled boat dataset delivery

The prepared dataset is `Datasets/boat_adaptation_v1/` (generated data is ignored
by Git). A portable training ZIP is alongside it. The training entry point and
reproduction workflow are documented in `Tools/boat_dataset/README.md`.

Prepared image counts: train 3,178; validation 384; test 384. A further 291 old
validation images are reserved separately. Training includes 1,162 original
training images, 1,728 new full frames and 288 new mask-verified empty-water crops.
The 26 new episodes keep all cameras/time samples together in one split.

Class IDs match the existing checkpoint: `0=leader`, `1=follower`. No model was
trained or replaced. The old dataset was read without editing it. The original
training YAML's missing train.txt and validation entry are avoided by the new
portable YAML, which points directly at prepared image directories.

Verification completed:

- Linux capture player build succeeded with zero C# and shader errors.
- All 26 episodes completed (2,496 full camera frames).
- Every full-frame YOLO label matched the corresponding instance-mask bounds
  and class mapping, with valid normalized coordinates and image dimensions.
- Train/validation/test have disjoint episode IDs and no exact image duplicates.
- Ultralytics 8.4.28 loaded every train/validation/test image and label with zero
  corrupt files: 4,474 / 790 / 746 annotated instances respectively.
- Sampled label overlays, including near/far, glare and partial views, were
  visually inspected. Copies of the previews and audit are in this directory.

The annotation policy is mesh visibility through transparent spray, with ocean
and opaque-object occlusion; foam/spray are not annotated as boats. Tiny fragments
below the documented threshold are omitted. The new validation/test frames all
contain boats; whole empty-ocean episode performance still needs checking.
Real tracking improvement is not claimed before training and controller tests.

The opt-in runtime exporter is in `Assets/DatasetCapture/`. It does not activate
in ordinary Play mode. Its isolated capture player disables camera networking,
uses private UDP ports and drives formation independently of detector outputs.

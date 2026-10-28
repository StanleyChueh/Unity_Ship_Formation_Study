# Automatically labeled boat adaptation dataset

This workflow creates camera images and YOLO detection labels from Unity boat
identity. It does not train a model, replace `best_v2.pt`, or change Python
tracking behavior. Normal Play mode is unaffected: the capture component runs
only with the `-usvdataset <job.json>` player argument.

The prepared dataset is in `Datasets/boat_adaptation_v1/`. Start with its
`train-preview.jpg`, `val-preview.jpg`, `test-preview.jpg` and `audit.json`.

## Train when ready

For free Google Colab, upload `Boat_Adaptation_Free_Colab.ipynb` to Colab and put
the prepared training ZIP in the top level of My Drive. Select a GPU runtime and
run its cells in order. It uses batch 8, extracts images to local Colab storage,
saves checkpoints/logs directly to Drive and resumes an interrupted run from
`last.pt`. Completed checkpoints are detected rather than silently retrained.
The notebook includes final-test and model-download cells. Free GPU allocation
and session duration are not guaranteed. See the notebook for paths and details.

From the Unity project directory, with the existing `unity_boat` environment:

```bash
conda activate unity_boat
python Tools/boat_dataset/train.py
```

The script starts a fresh fine-tuning run from `best_v2.pt`, using mixed old and
new training images. It uses 640-pixel model input to match current inference,
50 maximum epochs, early stopping, AdamW and a 0.001 initial learning rate.
These are starting settings, not a claim of optimal hyperparameters. If GPU
memory is insufficient, use `--batch 8` or `--batch 4`. Increasing `--imgsz`
should also be evaluated at the corresponding inference size and latency.

The new checkpoint is saved under `runs/boat_adaptation/finetune*/weights/`.
The original checkpoint stays in place. Evaluate the new `best.pt` on `test`
after selecting training settings on `val`:

```bash
yolo detect val model=runs/boat_adaptation/finetune/weights/best.pt data=Datasets/boat_adaptation_v1/data.yaml split=test imgsz=640
```

Adjust the run directory if Ultralytics appended a number. Keep the test set
out of training and hyperparameter tuning. Use `legacy_val.yaml` separately to
check whether the model still recognizes the old environment. Then compare
old and new checkpoints in the actual formation controller: class confusion,
wrong-target switches, fresh detection gaps and formation error all matter.
Dataset preparation alone does not establish that formation failures are fixed.

## Dataset and annotation policy

- Class IDs are unchanged: `0=leader`, `1=follower`.
- There are 26 independent capture episodes: 18 train, four validation, four
  test. All four cameras from a given episode stay in the same split.
- Captures vary near/far and staggered positions, straight/left/right motion,
  heading, sunlight, water direction/height, wake and spray strength.
- Most RGB images use the stream's native 640x360 / JPEG quality 55. A subset
  uses 960x540 / quality 75. The RGB image is captured without prediction boxes.
- The identity shader renders boat mesh instances into an unlit, non-antialiased
  linear ID target. Depth testing accounts for other opaque geometry and the
  ocean, including shared wave and wake displacement. Boxes enclose the
  remaining visible mesh pixels and clip at the image border.
- Transparent spray is deliberately excluded as a hard mask occluder: spray can
  cover an RGB hull while its hull label remains. Foam and spray are not included
  in boat boxes. This is an explicit through-spray annotation policy, not a claim
  that transparent occlusion is perfectly measured. Spot-check heavy-spray views.
- All visible boat instances are annotated, including visible pieces of the
  camera's own vessel. `camera_owner` and `truncated` are recorded in metadata.
  Anything below 16 visible mask pixels or a three-pixel box side is ignored.
- Legacy manual training images are copied into train with a `legacy_train_`
  prefix. Original validation images are reserved under `legacy_val/`; their
  original episode grouping is unknown, so they are evaluated separately.
- Exact image-file duplicates are removed across the prepared splits. New
  validation/test frames get priority. The audit records all dropped files.
- Training also includes empty sky/water crops from new training episodes.
  Every crop is checked to contain zero boat-mask pixels, including tiny boat
  fragments. Crop provenance is retained. Validation and test use full frames.

Identity labels are used only for offline training and evaluation. They are
not sent to the live controller. The existing source dataset is read-only.

## Reproduce or extend the capture

```bash
python Tools/boat_dataset/generate_dataset.py --smoke --work /tmp/usv-dataset-smoke-new
python Tools/boat_dataset/prepare_dataset.py --smoke --root /tmp/usv-dataset-smoke-new/smoke
python Tools/boat_dataset/generate_dataset.py --output Datasets/boat_adaptation_v2 --work /tmp/usv-dataset-v2
python Tools/boat_dataset/prepare_dataset.py --root Datasets/boat_adaptation_v2
```

Generation copies Assets, Packages, ProjectSettings and the import cache into
an isolated project. It builds a Linux player using the Unity executable given
by `--unity` (default is this machine's 2022.3.62f3). It needs a graphical Unity
session/GPU and briefly opens a small player window for each capture episode.
No camera stream is sent. Private UDP listeners avoid the real editor/controller.
Follower motion is driven by a diagnostic controller independently of YOLO, so
bad detections cannot prevent collection of useful adaptation examples.

`--resume --no-build` skips complete episodes with an unchanged plan. It refuses
to overwrite partial episodes. Preserve a partial run and choose a new output
directory, or remove that incomplete run deliberately before resuming. A plan
change requires a new output directory. `--samples` changes samples per episode.

Raw captures under `raw/` include JPEGs, instance masks, JSONL frame metadata,
job settings, completion markers and player logs. Prepared train/val/test
images and labels can be used independently of raw captures. YAML paths resolve
relative to their file, so the prepared dataset can be moved to another machine.

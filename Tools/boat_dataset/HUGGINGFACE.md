# Clean Hugging Face uploads

Prepared locally; nothing has been published.

Dataset upload source: `Datasets/boat_adaptation_v1_yolo/`

```text
data.yaml
train/
  images/
  labels/
val/
  images/
  labels/
test/
  images/
  labels/
```

Only paired images/YOLO labels and portable YAML are included. There are 3,178
train, 384 validation and 384 test images. Masks, raw captures, caches, previews,
audit files, legacy validation, notebooks and model weights are excluded.
Checksums and export validation are saved separately under Documentation.

Model upload source: `Datasets/boat_detector_starting_model/`. It contains only
`best_v2.pt`, the original model from before adaptation training. It is not a
newly trained adaptation checkpoint. After training, upload the new `best.pt`
to its own model repository or clearly distinguish it from these starting weights.

## Upload from the device with a stable connection

Copy the clean folders to that device. Alternatively, extract
`boat_adaptation_v1_yolo_clean.zip` to obtain the clean dataset folder, and copy
`best_v2.pt` separately. Use separate Hub repositories for data and weights:

```bash
python -m pip install --upgrade huggingface_hub
hf auth login
hf upload YOUR_USERNAME/boat-adaptation-yolo ./boat_adaptation_v1_yolo . --repo-type dataset --private
hf upload YOUR_USERNAME/boat-detector-starting ./boat_detector_starting_model . --repo-type model --private
```

Replace YOUR_USERNAME and run from the directory containing the two copied
folders. The commands create private repositories if missing; the private flag
does not change an existing repository's visibility. Choose visibility on the
Hub as appropriate. Authenticate interactively; no token belongs in these files.
If an upload is interrupted, rerun the same command; already uploaded data can
be skipped according to the installed Hub client's behavior.

[Official upload guide](https://huggingface.co/docs/huggingface_hub/en/guides/upload)

## Read the uploaded data in Colab

The existing Drive/ZIP notebook expects the earlier combined training ZIP,
including its starting weights and a fixed checksum. The new clean ZIP is for
the dataset alone and is not a drop-in replacement for that combined ZIP.

For separate Hugging Face repositories, after installing huggingface_hub:

```python
from huggingface_hub import notebook_login, snapshot_download, hf_hub_download

# Needed for private repositories; use your Hugging Face account/token prompt.
notebook_login()

dataset_dir = snapshot_download(
    repo_id="YOUR_USERNAME/boat-adaptation-yolo",
    repo_type="dataset",
    local_dir="/content/datasets/boat_adaptation_v1",
)
starting_model = hf_hub_download(
    repo_id="YOUR_USERNAME/boat-detector-starting",
    filename="best_v2.pt",
    repo_type="model",
)
```

Use `Path(dataset_dir) / "data.yaml"` for DATA_YAML and `Path(starting_model)`
for STARTING_MODEL in the training notebook. The ZIP-copy/extraction cells are
then unnecessary; keep Drive mounting and Drive checkpoint saving. Do not place
download caches or checkpoints back in the clean dataset upload folder.

## Re-export from prepared data

```bash
python Tools/boat_dataset/export_huggingface.py
```

The exporter uses an allowlist, validates label coordinates and image/label
pairing, verifies copied-file checksums and checks ZIP integrity/content. It
refuses nonempty destinations. Choose different --dataset-output / --model-output
paths to produce another clean export without mixing older files. It does not
authenticate, upload or train.

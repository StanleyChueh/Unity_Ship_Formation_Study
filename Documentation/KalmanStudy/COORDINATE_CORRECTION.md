# Evaluation metadata correction found by the audit

After the original60 runs completed, the audit correctly rejected out-of-bounds
ID-mask bounding boxes. Inspection found a single deterministic serialization
error in the frozen `StudyRig.IdBoxes`: the render and scan use1280x720, but the
returned top-left y coordinate uses `359 - y1` from an earlier360p pilot instead
of `719 - y1`. Thus **every logged ID-box y coordinate is360 pixels too small**.
Box x, width, height, ID and pixel count are unchanged. Actual RGB rendering,
YOLO boxes, selected measurements, controller inputs, physics and all world-pose
formation outcomes are unaffected. ID masks are never used for control.

`analyze.load` adds360 to each ID-box y in memory and retains `_raw_y`; original
steps.jsonl files are never rewritten. It records the correction in derived
summaries and audit output. Identity-overlap statistics and camera overlays must
be regenerated through this reader. Triangle formation IoU is computed from
world positions, so the published primary RMSE and triangle IoU do not change.
Horizontal-offset/area replay scores use x and width/height only and are also
unaffected. The frozen source and its bug remain archived for independent audit.

The replacement development reuses the same exact Unity binary, so the same
coordinate correction applies there. Any future corrected binary must declare
`id_box_encoded_y_origin=719` in its job/manifest to prevent double correction.
The default359 convention applies only to these fixed-step harness logs, not to
the separate native-app observer, which already uses height-1 correctly.

# Python Setup

Create the Conda environment:

```bash
conda env create -f environment.yml
conda activate unity_boat
```

Or install with pip only:

```bash
pip install -r requirements.txt
```

# Usage

Run Controller(Keyboard or Trajectory following)

```bash
cd Assets
python usv_controller.py
```

> **Note**
> 
> User can set Control mode to Keyboard or Trajectory following mode in config.py
> 
> By setting ```LEADER_INITIAL_CONTROL_MODE = "Trajectory"``` or ```LEADER_INITIAL_CONTROL_MODE = "Keyboard"``` to switch control mode.
> 
> Set trajectory mode: ```LEADER_TRAJECTORY_MODE = "Circle"``` or ```LEADER_TRAJECTORY_MODE = "Straight"```
## Run evaluation matrices

```
python usv/plot_metrics_comparison.py 
```

# Codebase

## USV Controller (Modular Split)

Callable functions for usv_controller.py 

Modules
-------
- `config.py`: all tunable constants and ports.
- `state.py`: shared runtime state and thread locks.
- `helpers.py`: common utility helpers and drawing helpers.
- `vision.py`: TCP camera receive + YOLO/depth/wake processing thread.
- `control.py`: vision-based control logic and command output.
- `app.py`: startup wiring, main loop, and UI loop.

-------
```text
usv_controller.py
└── calls usv.app.main()

usv/
├── __init__.py
│   └── exports main
│
├── app.py
│   ├── creates UDP sockets
│   ├── creates OpenCV windows
│   ├── starts TCP camera receiver threads
│   ├── starts central vision processing thread
│   ├── runs main control loop
│   ├── calls process_boat_vision_based() for Left boat
│   ├── calls process_boat_vision_based() for Right boat
│   └── displays processed frames
│
├── config.py
│   ├── UDP / TCP port settings
│   ├── camera stream configuration
│   ├── YOLO model settings
│   ├── wake detection parameters
│   ├── tracking / prediction parameters
│   └── controller parameters
│
├── state.py
│   ├── vision_lock
│   ├── frame_lock
│   ├── vision_states
│   ├── latest_frames
│   ├── display_frames
│   ├── formation_targets
│   └── controller_states
│
├── vision.py
│   ├── tcp_camera_receiver_thread()
│   ├── cv_processing_thread()
│   ├── detect_stern_wake()
│   ├── fuse_track_sources()
│   ├── lock_visual_reference()
│   ├── update_track_prediction()
│   ├── configure_yolo_runtime()
│   └── warmup_yolo_runtime()
│
├── control.py
│   ├── process_boat_vision_based()
│   ├── compute_pair_catchup_boost()
│   ├── get_tracking_gains()
│   ├── normalize_area_error()
│   ├── shape_area_error()
│   ├── compute_centered_cruise_throttle()
│   ├── compute_turn_catchup_boost()
│   └── compute_visual_far_boost()
│
└── helpers.py
    ├── recv_exact()
    ├── make_status_frame()
    ├── clamp()
    ├── blend_value()
    ├── get_peer_boat_side()
    ├── filter_steer_command()
    ├── draw_labeled_box()
    ├── draw_prediction_arrow()
    └── apply_camera_shake()
```

Entrypoint
----------
- Run `Assets/usv_controller.py`.


# Setup and push
Setup once

```
sudo apt install git-lfs
git lfs install
```

Track large files

```
git lfs track "*.zip"
git lfs track "*.pt"
git lfs track "*.mp4"
```

Add files
```
git add .gitattributes

git add .
```

Commit and push
```
git commit -m "message"

git push origin main
```
 




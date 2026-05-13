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

```bash
cd Assets
python usv_controller.py
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
 




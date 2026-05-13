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

# Usage

```
cd Assets
python usv_controller.py
```

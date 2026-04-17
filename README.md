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

# Usage

```
cd Assets
python usv_controller.py
```

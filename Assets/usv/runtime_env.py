"""Runtime environment helpers for GUI dependencies."""

import os
from pathlib import Path


def configure_qt_fontdir():
    """Point Qt at a real font directory when OpenCV's bundled path is missing."""
    current_fontdir = os.environ.get("QT_QPA_FONTDIR")
    if current_fontdir and Path(current_fontdir).is_dir():
        return

    font_candidates = (
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation2"),
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts"),
    )
    for font_dir in font_candidates:
        if font_dir.is_dir():
            os.environ["QT_QPA_FONTDIR"] = str(font_dir)
            return

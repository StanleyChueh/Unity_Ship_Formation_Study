"""USV package bootstrap."""

from .runtime_env import configure_qt_fontdir

configure_qt_fontdir()

try:
    from .app import main
    __all__ = ["main"]
except ImportError:
    # Runtime deps (cv2, etc.) not available; plotting-only usage is still fine.
    __all__ = []

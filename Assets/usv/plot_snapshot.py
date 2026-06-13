"""Backward-compatible entrypoint for snapshot plotting.

Use this script name if older docs/commands refer to `plot_snapshot.py`.
"""

import sys
from pathlib import Path

# When executed as a script (not as a package), ensure the parent directory
# that contains the `usv` package is on sys.path so absolute imports work.
if __package__ is None:
    parent = Path(__file__).resolve().parent.parent
    parent_str = str(parent)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)

try:
    from .plot_snapshots import main
except Exception:
    from usv.plot_snapshots import main


if __name__ == "__main__":
    main()

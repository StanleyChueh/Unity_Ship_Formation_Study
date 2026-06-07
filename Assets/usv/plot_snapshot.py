"""Backward-compatible entrypoint for snapshot plotting.

Use this script name if older docs/commands refer to `plot_snapshot.py`.
"""

try:
    from .plot_snapshots import main
except Exception:
    from plot_snapshots import main


if __name__ == "__main__":
    main()

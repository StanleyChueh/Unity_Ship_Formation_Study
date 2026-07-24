USV Controller (Modular Split)
==============================

This package is a first-pass non-breaking split from `Assets/usv_controller.py`.

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
- Keep running `Assets/usv_controller.py` as before.
- It now delegates to `usv.app.main()`.

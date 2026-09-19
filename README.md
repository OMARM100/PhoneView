# PhoneView

Python desktop application for Android screen viewing and control.

## Current version
v0.1.0 — USB / ADB foundation.

## Development
- Python
- PySide6
- ADB
- scrcpy
- VS Code
- Git / GitHub

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Connect an Android phone with USB Debugging enabled, accept the RSA prompt, then use Refresh and Connect / View.

## Roadmap
- Embedded phone display
- USB performance tuning
- Wi-Fi connection
- Input manager
- Multi-touch
- Overlay controls

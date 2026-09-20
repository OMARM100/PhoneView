# PhoneView — Project State / Resume Document

> **Purpose:** This file is the hand-off document for the current PhoneView development state.
> If development is paused and resumed later, read this file first before changing code.
>
> **Last documented branch:** `feat/ui-button-manager-project-window`
> **Last documented commit:** `cbc42589149eabee686f29cf3f171a2b6fc78f40`
> **Last documented commit message:** `Fix missing Mouse Look relative-mode implementation`
> **Status:** Development paused intentionally. This is a working development branch, not a final release.

---

## 1. Project identity

**PhoneView** is a Python/PySide6 desktop application for Android screen viewing and control.

The project has evolved beyond the original simple ADB/scrcpy launcher. The current development direction is:

- A real PhoneView desktop window.
- Android video rendered through SDL3.
- Pinned/vendored scrcpy source instead of downloading or auto-updating upstream code.
- Native desktop toolbar/header integrated into the PhoneView window.
- In-app control-mapping editor.
- Touch-style keyboard, mouse, joystick and camera/LOOK controls.
- Persistent control mappings.
- Automatic dependency/build handling.

### Main stack

- Python
- PySide6
- GTK3 for the native PhoneView/scrcpy-side window UI
- X11 for the embedded SDL child window on Linux
- SDL3
- C
- ADB
- scrcpy 4.1 source vendored inside the repository
- Meson/Ninja
- Git/GitHub

---

## 2. Important architecture decision

Do **not** redesign the project back into an external overlay.

The intended architecture is:

```
PhoneView Python App
        |
        +-- ADB / dependency management
        |
        +-- vendored scrcpy 4.1
                |
                +-- real PhoneView GTK top-level window
                |       |
                |       +-- native title/header
                |       +-- native toolbar
                |       +-- status area
                |
                +-- X11 child window
                        |
                        +-- SDL3 renderer
                                |
                                +-- Android video
                                +-- PhoneView control rendering
                                +-- touch/mouse/keyboard mapping
```

The toolbar must remain a **real desktop UI**, not graphics painted over the Android video.

The Android screen itself remains SDL-rendered.

---

## 3. Current project location

Local working directory used during development:

```text
~/Desktop/PhoneView/PhoneView
```

Main branch currently being developed:

```text
feat/ui-button-manager-project-window
```

GitHub repository:

```text
OMARM100/PhoneView
```

Pull request associated with the work:

```text
PR #6
```

---

## 4. Current source layout

Important project files:

```text
PhoneView/
├── app.py
├── config.py
├── requirements.txt
├── core/
│   ├── adb_manager.py
│   ├── dependency_checker.py
│   ├── scrcpy_installer.py
│   └── scrcpy_manager.py
├── ui/
│   ├── main_window.py
│   └── setup_window.py
└── vendor/
    └── scrcpy/
        └── v4.1/
            └── app/
                ├── src/
                └── data/
                    ├── phoneview.css
                    └── phoneview.svg
```

Important scrcpy-side PhoneView files:

```text
vendor/scrcpy/v4.1/app/src/phoneview_ui.c
vendor/scrcpy/v4.1/app/src/phoneview_ui.h
vendor/scrcpy/v4.1/app/src/screen.c
vendor/scrcpy/v4.1/app/src/screen.h
vendor/scrcpy/v4.1/app/data/phoneview.css
vendor/scrcpy/v4.1/app/data/phoneview.svg
```

---

## 5. Python application state

### `app.py`

The application now automatically bootstraps the project virtual environment when necessary.

Important behavior:

- Creates `.venv` if it does not exist.
- Uses `requirements.txt`.
- Detects missing PySide6.
- Re-executes itself using the project virtual environment.
- This means running `python3 app.py` is intended to be enough from the project directory.

Current Python dependency:

```text
PySide6==6.7.3
```

### Main UI

`ui/main_window.py` remains the Python-side main application window.

`ui/setup_window.py` is the dependency/setup window.

The setup window has a custom dark PhoneView visual design and custom scrollbar styling.

---

## 6. Setup / installation window

The installer/setup page was redesigned with a dark blue/black PhoneView theme.

Current design language:

- Background: `#0B0F19`
- Cards: `#111827`
- Blue primary accent
- Rounded cards
- Custom progress bar
- Dependency status rows
- Activity log
- Primary/Quiet buttons
- Custom vertical and horizontal scrollbars
- Blue pressed scrollbar handle
- No reliance on the default white Qt scrollbar appearance

The supplied QSS is intentionally kept inside `ui/setup_window.py` as `PHONEVIEW_QSS`.

If the installer is changed later, preserve this visual language unless a new design is explicitly requested.

---

## 7. scrcpy build strategy

The project uses a **vendored pinned scrcpy 4.1**.

Important rule:

> Do not reintroduce automatic upstream scrcpy downloading/updating.

The PhoneView installer builds the vendored source and tracks the source state.

Persistent caches were intentionally introduced because the user does not want every modification to cause a full rebuild.

### Persistent cache locations

SDL3:

```text
~/.cache/phoneview/sdl3/3.4.12/linux-native-shared
```

scrcpy:

```text
~/.cache/phoneview/scrcpy/v4.1-phoneview-native-toolbar/
```

Incremental build tree:

```text
~/.cache/phoneview/scrcpy/v4.1-phoneview-native-toolbar/build-v2
```

Installed PhoneView scrcpy:

```text
~/.local/share/phoneview/scrcpy/v4.1-phoneview-native-toolbar
```

Launcher:

```text
~/.local/bin/scrcpy-phoneview
```

### Critical build rule

**Never use `rm -rf` on the PhoneView SDL/scrcpy build caches just to rebuild.**

The installer is designed to detect source changes and rebuild incrementally.

---

## 8. Linux display architecture

Current implementation targets Linux/X11 for the native embedded scrcpy window.

The architecture uses:

1. GTK3 top-level PhoneView window.
2. A video container inside that window.
3. An X11 child window.
4. SDL3 wrapping that X11 child window.
5. Android frames rendered by SDL3.

The X11 child explicitly receives relevant input/focus events.

The implementation added X11 input masks for:

- ButtonPress
- ButtonRelease
- PointerMotion
- EnterWindow
- LeaveWindow
- FocusChange

SDL's X11 external-window input path is also explicitly enabled.

---

## 9. Native PhoneView window UI

The current PhoneView window contains a real native desktop interface.

Conceptually:

```text
┌──────────────────────────────────────────────┐
│ PhoneView / project / device          ─ □ × │
├──────────────────────────────────────────────┤
│ Edit | Add Button | Save | Duplicate | ...  │
├──────────────────────────────────────────────┤
│                                              │
│                 Android Screen               │
│                                              │
└──────────────────────────────────────────────┘
```

The UI is not an overlay process.

### Current toolbar actions

- Edit
- Add Button
- Save
- Duplicate
- Delete
- Done

### Add Button menu currently supports

- Keyboard Key — Hold
- Keyboard Key — Tap
- Keyboard Key — Toggle
- Mouse Button
- Mouse Look / Camera
- Mouse Wheel
- Virtual Joystick — WASD

---

## 10. Control system currently implemented

Controls are stored in the PhoneView control model in `screen.h`.

The control model currently supports:

- label
- keyboard key
- type
- mouse button
- behavior
- joystick direction keys
- position X/Y
- size
- sensitivity
- speed
- LOOK activation source
- runtime position/state

Control types currently include:

```text
keyboard
mouse
look
wheel
joystick
```

---

## 11. Keyboard controls

Keyboard mappings support:

### Hold

Pressing the physical key sends Android touch DOWN.

Releasing the physical key sends Android touch UP.

### Tap

A key press produces a DOWN followed immediately by an UP.

### Toggle

First press activates the touch.

Second press releases it.

Keyboard mappings can coexist with other mappings.

Physical key capture is available in the editor dialog.

Examples of normalized key names include:

```text
Space
Left Shift
Left Ctrl
A
B
...
```

---

## 12. Mouse controls

Mouse Button controls are supported with:

- hold
- tap
- toggle

The mapping is translated into Android touch input at the configured screen position.

---

## 13. Virtual joystick / WASD

A virtual joystick control is implemented.

Default joystick mapping:

```text
Up    = W
Left  = A
Down  = S
Right = D
```

The joystick supports:

- four-direction movement
- diagonal movement
- runtime visual knob
- configurable visual size
- position on the Android screen
- keyboard-driven Android touch movement

The joystick was specifically designed to behave as a scalable touch-style control rather than merely being a decorative circle.

### Known state

The joystick has been implemented and is functional enough to continue development from here, but it should be regression-tested after future changes to input dispatch or resizing.

---

## 14. Mouse Look / Camera — current state

Mouse Look is the most recently worked-on subsystem.

The intended behavior is:

1. A user places a LOOK control on the Android screen.
2. The user chooses an activation source.
3. Holding the activation key/button activates LOOK.
4. The mouse becomes hidden/captured and relative movement is used.
5. A virtual Android pointer starts exactly at the LOOK control position.
6. Mouse movement moves that Android pointer.
7. The pointer can be moved continuously without being limited by the PhoneView window edge.
8. Releasing the activation key/button ends LOOK and releases relative mouse mode.

### Important recent improvement

LOOK is no longer conceptually restricted to the physical mouse button.

The editor now supports:

```text
Activate With:
    Keyboard Key
    Mouse Button
```

This allows a keyboard key to enter/exit LOOK while the physical mouse remains available for normal left/right clicking.

This was added specifically because the desired behavior is:

> Any chosen activation key can enter LOOK, while the mouse can still move and be used for left/right click actions.

### LOOK settings

The editor now has:

- Activation source
- Keyboard key
- Mouse button
- Sensitivity
- Speed

Sensitivity range is intended to be adjustable up to 10.0.

Speed range is intended to be adjustable up to 5.0.

The runtime gain uses both values.

### Default new LOOK mapping

New LOOK controls default to:

```text
Activation = Keyboard
Key        = Right Shift
Sensitivity = 1.6
Speed       = 1.0
```

This is intentional so left/right mouse buttons remain available.

### Compatibility

Older LOOK configurations that used a mouse button are migrated by reading the old `mouse_button` value when `look_activation` is missing.

---

## 15. Mouse Look input implementation details

The current implementation uses:

- X11 external-window input support.
- SDL mouse capture.
- SDL relative mouse mode.
- Hidden cursor while active.
- Relative mouse delta polling.
- A PhoneView runtime pointer position.
- Android touch MOVE events at the runtime pointer position.

The current runtime pointer is clamped to the normalized Android screen:

```text
X = 0.01 ... 0.99
Y = 0.01 ... 0.99
```

When LOOK is active, mouse motion is consumed by the PhoneView LOOK subsystem rather than normal absolute pointer handling.

---

## 16. Control editor

Double-clicking a control opens the control editor.

The editor supports configuration of relevant properties such as:

- label
- keyboard key
- behavior
- mouse button
- joystick direction keys
- size
- sensitivity
- LOOK speed
- LOOK activation source
- LOOK keyboard key
- LOOK mouse button

Physical keyboard capture is implemented for key-entry widgets.

---

## 17. Control positioning

Implemented editing interactions include:

- select a control
- drag a control
- direct visual resize using the resize handle
- double-click to edit
- right-click delete
- Delete / Backspace delete selected control
- Arrow keys move selected control
- Shift + Arrow moves selected control farther
- Escape clears selection
- Duplicate creates an offset copy

The resize handle is drawn at the bottom-right of the selected control.

Direct visual resizing was specifically fixed after it initially only worked through the editor dialog.

---

## 18. Control persistence

Mappings are persisted in:

```text
~/.config/PhoneView/controls.json
```

The JSON model currently stores properties including:

```text
label
key
type
x
y
size
sensitivity
speed
behavior
mouse_button
up_key
left_key
down_key
right_key
look_activation
```

Older files should continue to load with defaults for newer fields.

---

## 19. Android aspect ratio / resizing

PhoneView keeps the Android display aspect ratio when the desktop window is resized.

The Android content rectangle is calculated and centered inside the available video area.

Important behavior:

- The outer PhoneView window can resize.
- The Android content remains correctly letterboxed/centered.
- PhoneView resizing does not unnecessarily request a new Android display size.
- Rendering falls back correctly when SDL output dimensions are needed.

---

## 20. Toolbar text layout

A recent issue was that toolbar text could wrap/overlap even though horizontal space existed.

The toolbar was adjusted to:

- slightly increase toolbar height
- reduce button margins
- use controlled minimum widths
- make labels single-line
- ellipsize labels where necessary
- constrain label width
- keep project/status text single-line

The goal is that labels remain visually stable instead of stacking letters on top of each other.

---

## 21. Setup scrollbar

The setup page now has custom QSS for:

- vertical scrollbar
- horizontal scrollbar
- handle
- hover state
- pressed state
- transparent add/sub pages
- hidden arrow buttons

This replaces the unwanted default white scrollbar appearance.

---

## 22. Visual assets

PhoneView has a custom SVG asset:

```text
vendor/scrcpy/v4.1/app/data/phoneview.svg
```

and custom PhoneView stylesheet:

```text
vendor/scrcpy/v4.1/app/data/phoneview.css
```

The stylesheet is used by the native GTK PhoneView UI.

---

## 23. Important fixes already made during this development phase

The following classes of issues have already been addressed:

- Missing PySide6 when launching with system Python.
- Automatic virtual-environment bootstrap.
- scrcpy missing from PATH.
- Persistent scrcpy build/install handling.
- Persistent SDL3 build cache.
- Relocation of SDL pkg-config metadata out of temporary paths.
- Vendored source change detection.
- Forward declaration ordering in `screen.c`.
- Native GTK PhoneView window.
- Embedded SDL/X11 Android display.
- Real native toolbar instead of a painted overlay.
- Button mapping creation.
- Keyboard hold/tap/toggle.
- Mouse button mapping.
- Virtual joystick.
- Joystick diagonal handling.
- Control selection.
- Control dragging.
- Control resizing.
- Resize handle hit detection.
- Duplicate control.
- Delete control.
- Double-click editor.
- Physical keyboard capture.
- Persistent JSON mapping.
- Android aspect-ratio resizing.
- Toolbar styling.
- Toolbar label wrapping/overlap.
- Custom setup page styling.
- Custom setup scrollbar.
- Initial Mouse Look implementation.
- X11/SDL external-window input improvements.
- Mouse capture/relative mode improvements.
- LOOK activation by keyboard key.
- LOOK sensitivity setting.
- LOOK speed setting.

---

## 24. Current known unfinished / next-work areas

These are **not marked as completed** and should be treated as the next work queue.

### A. Mouse Look final validation

The latest Mouse Look changes were made directly in the repository, but the final runtime behavior still needs a real end-to-end test on the development machine.

Test:

1. Add LOOK.
2. Set activation to a keyboard key.
3. Hold the key.
4. Confirm mouse disappears.
5. Move mouse continuously in all directions.
6. Confirm the Android touch pointer moves.
7. Confirm the pointer starts at the configured LOOK position.
8. Confirm physical left/right mouse clicking remains usable as intended.
9. Release activation key.
10. Confirm cursor returns and normal mouse input resumes.
11. Test sensitivity values.
12. Test speed values.

Do not mark Mouse Look "finished" until this test passes.

### B. Joystick regression test

Test:

- W
- A
- S
- D
- W+A
- W+D
- S+A
- S+D
- joystick resizing
- joystick movement after window resize

### C. Mapping UX redesign

The Add Button system is functional but was previously described as not practical enough.

Future work should focus on making button creation faster and clearer rather than adding more menu complexity.

Possible direction:

- cleaner category selection
- immediate visual placement
- fewer modal steps
- better distinction between Keyboard / Mouse / Camera / Joystick
- clearer defaults
- possibly a quick-add workflow

Do not replace the whole system without preserving the existing mapping model.

### D. Control visual scaling

Small controls can make their text/icons look poor at very small sizes.

Future work should improve:

- text scaling
- icon scaling
- minimum readable size
- hiding or simplifying labels when a control becomes extremely small
- preserving visual quality during resizing

Do not solve this by simply forcing every control to remain huge.

### E. Build/test verification

After future C changes, always perform an incremental PhoneView build.

Do not delete the persistent build caches.

### F. Packaging / distribution

Not complete.

Future work may include:

- proper Linux packaging
- portable distribution
- dependency handling improvements
- Windows support if desired later
- release versioning
- user documentation

---

## 25. Known development constraints

### Do not remove these intentionally

- Vendored scrcpy 4.1.
- Persistent SDL cache.
- Persistent scrcpy build cache.
- Native GTK toolbar architecture.
- SDL3 Android renderer.
- X11 embedding approach unless deliberately replacing the Linux window architecture.
- JSON mapping persistence.
- Existing keyboard/mouse/joystick control types.

### Avoid

- External overlay windows.
- Replacing the whole project with a separate implementation.
- Automatically updating scrcpy from upstream.
- Full cache deletion for normal source changes.
- Reverting to a toolbar painted inside the Android screen.

---

## 26. Standard run/update command

After a repository update, the normal development command is:

```bash
cd ~/Desktop/PhoneView/PhoneView && git fetch origin && git checkout feat/ui-button-manager-project-window && git reset --hard origin/feat/ui-button-manager-project-window && python3 app.py
```

This intentionally does **not** delete any build cache.

---

## 27. Resume procedure

When returning to this project after a pause:

### Step 1 — Read this file

Read:

```text
PROJECT_STATE.md
```

### Step 2 — Sync the branch

```bash
cd ~/Desktop/PhoneView/PhoneView && git fetch origin && git checkout feat/ui-button-manager-project-window && git reset --hard origin/feat/ui-button-manager-project-window
```

### Step 3 — Run PhoneView

```bash
python3 app.py
```

### Step 4 — Before changing code

Check the current branch head because this document records the state at the time it was written.

### Step 5 — Continue from the unfinished queue

Start with Mouse Look end-to-end validation unless the user explicitly chooses another task.

---

## 28. Current priority order

When development resumes, use this order unless the user changes it:

1. **Verify Mouse Look end-to-end.**
2. Fix any Mouse Look input/capture issues.
3. Regression-test joystick.
4. Improve Add Button UX.
5. Improve small-control icon/text scaling.
6. Run broader input regression tests.
7. Only then move toward packaging/release work.

---

## 29. Current project philosophy

PhoneView is no longer just a thin wrapper around scrcpy.

The current goal is a cohesive Android control/viewing desktop application where:

- scrcpy provides the proven Android transport/video foundation,
- PhoneView provides the desktop product UI,
- PhoneView provides the configurable game-control mapping layer,
- controls are persistent and editable,
- and the user can build custom touch layouts without external overlay software.

The project should be resumed from the current architecture rather than restarted from the original v0.1.0 README description.

---

## 30. Final checkpoint

At the time this document was created:

- The repository contains the substantial PhoneView native UI/control work described above.
- The active development branch is `feat/ui-button-manager-project-window`.
- The branch head recorded for this checkpoint is `cbc42589149eabee686f29cf3f171a2b6fc78f40`.
- Development is intentionally paused.
- The next developer session should begin by reading this document and validating the current build/runtime before making new architectural changes.

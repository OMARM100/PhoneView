# PhoneView — Comprehensive Project Information

Permanent handover document for the PhoneView project. Keep this file on the main branch. If development stops for a long time, this document is the first place to read before touching the code.

## Repository

Repository: OMARM100/PhoneView
Default branch: main
Active development branch: feat/ui-button-manager-project-window
Major native UI/button-manager work: PR #6

Main is the stable/reference branch. The feature branch contains the active PhoneView native-window, control-editor and mapping work.

## Project purpose

PhoneView is a Linux desktop application for Android screen viewing, control and game input mapping.

Original foundation:
- Python
- PySide6
- ADB
- scrcpy

Current direction:
- Native PhoneView desktop window
- Pinned/vendored scrcpy 4.1
- GTK3 native desktop UI
- X11 embedded video child window
- SDL3 Android rendering
- Integrated keyboard, mouse, joystick and touch mapping editor

The mapping editor is a core feature. It must be part of the real PhoneView desktop window. It must not become a separate overlay process and must not be painted as a fake toolbar inside the Android SDL frame.

## Architecture

Conceptual hierarchy:

    PhoneView GTK top-level window
    ├── native header/title
    ├── native toolbar
    └── video area
        └── X11 child window
            └── SDL3 renderer
                └── Android video

GTK owns the real desktop UI:
- title/header
- minimize/maximize/close
- toolbar
- editor dialogs
- status UI

X11 provides the embedded child window.

SDL3 renders Android video and participates in input handling.

Patched scrcpy contains PhoneView mapping/runtime logic.

## Important local paths

Project:
    ~/Desktop/PhoneView/PhoneView

Vendored scrcpy:
    vendor/scrcpy/v4.1

Native UI:
    vendor/scrcpy/v4.1/app/src/phoneview_ui.c
    vendor/scrcpy/v4.1/app/src/phoneview_ui.h

Mapping/runtime:
    vendor/scrcpy/v4.1/app/src/screen.c
    vendor/scrcpy/v4.1/app/src/screen.h

Native stylesheet:
    vendor/scrcpy/v4.1/app/data/phoneview.css

Native icon:
    vendor/scrcpy/v4.1/app/data/phoneview.svg

Python entry:
    app.py

Python dependencies:
    requirements.txt

Setup UI:
    ui/setup_window.py

Dependency checker:
    core/dependency_checker.py

scrcpy build/install manager:
    core/scrcpy_installer.py

Saved mappings:
    ~/.config/PhoneView/controls.json

## Python layer

Current Python dependency:
    PySide6==6.7.3

app.py contains automatic project .venv bootstrap behavior so python3 app.py can create/use the project environment when necessary.

Do not remove that behavior without a deliberate replacement.

## scrcpy strategy

The integrated runtime uses the pinned vendored source:

    vendor/scrcpy/v4.1

This is intentional because PhoneView patches scrcpy for:
- GTK integration
- X11 embedding
- SDL behavior
- mapping
- control rendering
- touch injection
- Mouse Look

Do not reintroduce automatic upstream replacement that overwrites the patched PhoneView runtime.

## Linux dependencies

Important dependencies:
- Python 3
- PySide6
- ADB
- GTK3 development libraries
- X11 development libraries
- SDL3
- Meson
- Ninja
- GCC/build toolchain

The current embedded native-window architecture expects X11.

## SDL3 cache

Pinned SDL3:
    3.4.12

Persistent cache:
    ~/.cache/phoneview/sdl3/3.4.12/linux-native-shared

A previous issue happened because sdl3.pc pointed into /tmp. The installer was changed to keep pkg-config metadata in the persistent cache.

Do not delete this cache during normal development.

## scrcpy build cache

Persistent build:
    ~/.cache/phoneview/scrcpy/v4.1-phoneview-native-toolbar/

Incremental build tree:
    ~/.cache/phoneview/scrcpy/v4.1-phoneview-native-toolbar/build-v2

Installed managed scrcpy:
    ~/.local/share/phoneview/scrcpy/v4.1-phoneview-native-toolbar

Launcher:
    ~/.local/bin/scrcpy-phoneview

The installer uses source stamping so vendored source changes can trigger incremental rebuilds.

IMPORTANT: do not use rm -rf against the PhoneView cache for ordinary source changes. Preserve the incremental cache.

## Normal development command

    cd ~/Desktop/PhoneView/PhoneView && git fetch origin && git checkout feat/ui-button-manager-project-window && git reset --hard origin/feat/ui-button-manager-project-window && python3 app.py

This synchronizes the development branch and starts PhoneView without deleting build caches.

## Control system

The mapping system is integrated into screen.c.

The control model contains:
- label
- key
- type
- mouse_button
- behavior
- up_key
- left_key
- down_key
- right_key
- x/y
- size
- sensitivity
- runtime_x/runtime_y
- active
- source_down
- joystick direction state

The current control array supports up to 64 controls.

Saved editor position and runtime position must remain separate.

## Supported controls

### Keyboard Key

Maps a keyboard key to an Android touch point.

Behaviors:
- Hold
- Tap
- Toggle

### Mouse Button

Maps a physical mouse button to an Android touch point.

### Mouse Look / Camera

FPS-style camera mapping.

Required behavior:
1. A configurable activation key/button enters LOOK.
2. The desktop cursor is hidden/captured.
3. Relative mouse movement becomes camera movement.
4. The Android touch pointer remains associated with the configured LOOK point.
5. Releasing activation exits LOOK and restores the cursor.

Activation is independent from mouse movement:
- keyboard key
- mouse button

This is important because keyboard activation allows left/right mouse buttons to remain available for other game actions.

LOOK needs configurable:
- sensitivity
- speed

### Mouse Wheel

Maps wheel actions.

### Virtual Joystick / WASD

Circular joystick controlled by four directions.

Default:
    W = Up
    A = Left
    S = Down
    D = Right

Diagonal combinations must work.

## Mapping coordinates

Controls use normalized Android-content coordinates:

    x = 0.0 ... 1.0
    y = 0.0 ... 1.0

Runtime movement must not permanently change the saved editor position.

## Editor

Implemented/expected:
- Add control
- Select
- Drag
- Direct visual resize
- Double-click edit
- Arrow-key movement
- Shift + Arrow for larger movement
- Duplicate
- Delete
- Save
- Done
- Escape clears selection

The resize handle must work directly on the rendered control, not only through the property dialog.

## Add Button

Toolbar categories:
- Keyboard Key — Hold
- Keyboard Key — Tap
- Keyboard Key — Toggle
- Mouse Button
- Mouse Look / Camera
- Mouse Wheel
- Virtual Joystick — WASD

The Add workflow is still an area for UX refinement. The desired direction is faster and clearer control creation.

## Keyboard capture

The editor supports physical key capture through GTK key events.

Examples:
- Space
- Left Shift
- Left Ctrl

Alphabetic keys are normalized.

The intended UX is to focus the key field and press the desired physical key.

## Behavior semantics

Hold:
    down -> ACTION_DOWN
    up -> ACTION_UP

Tap:
    press -> ACTION_DOWN then ACTION_UP

Toggle:
    first press -> ACTION_DOWN
    second press -> ACTION_UP

Multiple controls may share one physical key. The keyboard handler must not stop after the first match.

## Joystick

The joystick is real input mapping, not only a visual icon.

Test:
    W
    A
    S
    D
    W+A
    W+D
    S+A
    S+D

Also test releasing one direction while another remains active.

## Mouse Look debugging chain

When LOOK fails, inspect:

    physical activation
    -> X11 focus
    -> SDL event
    -> relative mouse mode
    -> relative mouse delta
    -> PhoneView LOOK handler
    -> runtime touch position
    -> ACTION_DOWN/MOVE/UP
    -> Android application

Do not assume a LOOK problem is only a UI problem.

## JSON persistence

Configuration:
    ~/.config/PhoneView/controls.json

Stored concepts:
- label
- key
- type
- x
- y
- size
- sensitivity
- behavior
- mouse_button
- up_key
- left_key
- down_key
- right_key
- look_activation
- speed

Old configuration files may not contain newer fields. Missing fields must receive safe defaults.

Typical defaults:
    size = 1.0
    sensitivity = 1.6
    speed = 1.0
    behavior = hold

Backward compatibility is required.

## Touch injection

Controls ultimately generate:
- ACTION_DOWN
- ACTION_MOVE
- ACTION_UP

LOOK keeps a pointer active while its activation source is held. Joystick controls update movement according to directional state.

## Rendering and resizing

Controls are rendered through the SDL/scrcpy rendering path.

Normal mode:
- controls are visually light

Edit mode:
- controls are clearer
- selection is visible
- resize handle is visible

The Android video must remain opaque.

PhoneView preserves Android aspect ratio. The Android frame is fitted and centered in the video area.

Desktop resizing must not accidentally request Android display resizing.

## Native toolbar

Actions:
- Edit
- Add Button
- Save
- Duplicate
- Delete
- Done
- status

It is a real GTK toolbar, not an SDL-painted overlay.

Known issue/history: toolbar labels could wrap or stack despite available space.

Correct direction:
- single-line labels
- ellipsizing when needed
- sensible minimum widths
- compact padding
- adequate toolbar height

Do not solve toolbar text overlap by unnecessarily shrinking the Android viewport.

## Native file responsibilities

phoneview_ui.c:
- GTK top-level window
- header/title
- toolbar
- X11 child
- SDL external-window integration
- editor dialogs
- key capture
- UI focus/status

phoneview_ui.h:
- UI structures
- add types
- UI actions
- editor data
- UI APIs

screen.c:
- runtime state
- control load/save
- keyboard mapping
- mouse mapping
- LOOK
- joystick
- touch injection
- rendering
- editor interaction

screen.h:
- control/state structures

phoneview.css:
- PhoneView desktop styling

phoneview.svg:
- PhoneView icon

## Editor state

Editor state contains concepts including:
- enabled
- edit_mode
- capture_mode
- dragging
- resizing
- capture_stage
- drag_index
- resize_index
- selected_index
- last_click_time
- last_click_index
- controls
- count

Keep temporary editor state separate from persistent control properties.

## Setup/install window

ui/setup_window.py contains PHONEVIEW_QSS.

Design direction:
- background #0B0F19
- cards #111827
- borders #1F2937 and #374151
- muted text #94A3B8
- main text #F1F5F9
- blue #3B82F6
- dark blue #2563EB
- light blue #60A5FA

The setup window should contain:
- dark cards
- blue progress bar
- dark activity log
- styled dependency rows
- styled scrollbars
- Primary button
- Quiet button

The scrollbar must not use the default white Qt appearance.

## Installer and dependency manager

core/scrcpy_installer.py handles:
- managed scrcpy build
- persistent cache
- source change detection
- incremental Meson/Ninja build
- installation
- launcher

core/dependency_checker.py handles dependency/runtime validity and managed scrcpy source-stamp checks.

Do not replace this with a blind delete-and-rebuild workflow.

## Historical build issue: sc_screen_render

Previous error:
    implicit declaration of function sc_screen_render
    conflicting types for sc_screen_render
    static declaration ... follows non-static declaration

Cause: sc_screen_render was used before its static forward declaration.

Required declaration:
    static void
    sc_screen_render(struct sc_screen *screen, bool update_content_rect);

It must appear before the first use.

## Historical harmless warning

Previous warning:
    phoneview_toggle_fullscreen defined but not used

This was not the fatal build error.

## Performance rules

The project is intended to work on older Intel integrated graphics.

Avoid:
- expensive full-screen effects
- unnecessary per-frame allocations
- expensive blur/glow
- duplicate video rendering
- external overlay windows
- CPU-heavy work in the video loop

Prefer:
- simple SDL primitives
- cached state/geometry where practical
- lightweight control rendering
- event-driven work

## Current test checklist

Android:
- ADB detection
- USB connection
- RSA authorization
- screen display

Window:
- resize
- maximize
- minimize
- close
- aspect ratio
- no background bleed

Toolbar:
- labels readable
- Add works
- Save works
- Duplicate works
- Delete works
- Done restores video focus

Controls:
- add
- select
- move
- resize
- double-click edit
- duplicate
- delete
- save/reload

Keyboard:
- hold
- tap
- toggle
- shared key

Mouse:
- left
- right
- middle where supported
- wheel

LOOK:
- keyboard activation
- mouse activation
- cursor hide
- relative motion
- continuous movement
- release
- cursor restore
- left/right click availability with keyboard activation
- sensitivity
- speed

Joystick:
- W/A/S/D
- diagonals
- release combinations
- visual knob
- size
- position

Persistence:
- save
- restart
- verify mappings survive

## Future roadmap

Potential future work:
1. Better Add Button workflow.
2. More polished editor.
3. Better joystick customization.
4. Separate horizontal/vertical LOOK sensitivity.
5. LOOK acceleration/smoothing.
6. Invert Y.
7. More LOOK activation modes.
8. Game-specific profiles.
9. Multi-touch improvements.
10. Wi-Fi ADB.
11. Multi-device selection.
12. Better USB performance tuning.
13. Packaging/distribution.
14. Better installer progress/reporting.

Possible profiles:
    Default
    Game A
    Game B
    Game C

## Product decisions to preserve

1. PhoneView is more than a scrcpy launcher.
2. The control editor is a core feature.
3. The editor belongs inside the real PhoneView window.
4. GTK is the native desktop UI layer.
5. X11 is the current embedding mechanism.
6. SDL3 remains the Android rendering/input layer.
7. Vendored scrcpy 4.1 is intentional.
8. Automatic upstream replacement must not overwrite the patched runtime.
9. Build caches must remain persistent.
10. Mappings must survive restarts.
11. LOOK activation must be configurable.
12. LOOK movement comes from physical mouse movement while active.
13. Keyboard LOOK activation should leave left/right mouse buttons available.
14. Low-end hardware performance matters.
15. Avoid external overlays.
16. Preserve old JSON compatibility.
17. Do not solve UI layout problems by unnecessarily shrinking the Android viewport.

## Recovery after shelving

If returning after a long pause:
1. Read this file.
2. Check git status.
3. Check branches and recent commits.
4. Check main and the development branch.
5. Do not clean caches immediately.
6. Run the existing application before changing architecture.
7. Test the existing build.
8. Read screen.c and phoneview_ui.c before modifying mapping behavior.
9. Read core/scrcpy_installer.py before changing build behavior.
10. Preserve old control JSON compatibility.

Useful commands:

    cd ~/Desktop/PhoneView/PhoneView
    git status
    git branch -a
    git log --oneline --decorate -20

Then:

    git fetch origin
    git checkout feat/ui-button-manager-project-window
    git reset --hard origin/feat/ui-button-manager-project-window
    python3 app.py

## Quick reference

Repository:
    OMARM100/PhoneView

Default:
    main

Development:
    feat/ui-button-manager-project-window

Local project:
    ~/Desktop/PhoneView/PhoneView

Vendored scrcpy:
    vendor/scrcpy/v4.1

Controls:
    ~/.config/PhoneView/controls.json

SDL cache:
    ~/.cache/phoneview/sdl3/3.4.12/linux-native-shared

scrcpy cache:
    ~/.cache/phoneview/scrcpy/v4.1-phoneview-native-toolbar/

Managed scrcpy:
    ~/.local/share/phoneview/scrcpy/v4.1-phoneview-native-toolbar

Launcher:
    ~/.local/bin/scrcpy-phoneview

Setup:
    ui/setup_window.py

Installer:
    core/scrcpy_installer.py

Dependency checker:
    core/dependency_checker.py

Native UI:
    vendor/scrcpy/v4.1/app/src/phoneview_ui.c
    vendor/scrcpy/v4.1/app/src/phoneview_ui.h

Runtime:
    vendor/scrcpy/v4.1/app/src/screen.c
    vendor/scrcpy/v4.1/app/src/screen.h

Styles:
    vendor/scrcpy/v4.1/app/data/phoneview.css

## Maintenance rule

Keep this file on main. Update it whenever architecture, important paths, dependencies, build behavior, control types, JSON schema, major bugs, testing state or roadmap changes.

The goal is that PhoneView can be understood and resumed without depending on old chat history.

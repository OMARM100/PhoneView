import re
import subprocess

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget


class MappingButton(QPushButton):
    moved = Signal()
    removed = Signal()

    def __init__(self, item, parent=None):
        super().__init__(str(item.get("label") or item.get("key") or "Button"), parent)
        self.item = item
        self.drag_start = None
        self.setCursor(Qt.OpenHandCursor)
        self.setFixedSize(76, 42)
        self.setStyleSheet("""
            QPushButton {
                background: rgba(32, 115, 229, 220);
                border: 2px solid rgba(255,255,255,210);
                border-radius: 10px;
                color: white;
                font-weight: 900;
                font-size: 12px;
                padding: 0 8px;
            }
            QPushButton:hover { background: rgba(58,130,240,235); }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self.removed.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start is None or not (event.buttons() & Qt.LeftButton):
            return
        delta = event.globalPosition().toPoint() - self.drag_start
        p = self.pos() + delta
        parent = self.parentWidget()
        if parent:
            x = max(0, min(parent.width() - self.width(), p.x()))
            y = max(0, min(parent.height() - self.height(), p.y()))
            self.move(x, y)
            self.item["x"] = x / max(1, parent.width())
            self.item["y"] = y / max(1, parent.height())
            self.moved.emit()
        self.drag_start = event.globalPosition().toPoint()
        event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_start = None
        self.setCursor(Qt.OpenHandCursor)
        event.accept()


class ScrcpyMappingOverlay(QWidget):
    changed = Signal()
    capture_finished = Signal(dict)

    def __init__(self, window_title, controls, parent=None):
        super().__init__(parent)
        self.window_title = window_title
        self.controls = controls
        self.capture_mode = False
        self.edit_mode = False

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.root = QWidget(self)
        self.root.setObjectName("OverlayRoot")
        self.root.setStyleSheet("""
            QWidget#OverlayRoot {
                background: rgba(5,9,15,55);
                border: 2px solid rgba(76,134,234,150);
                border-radius: 10px;
            }
            QLabel#OverlayTitle {
                color: white;
                font-size: 11px;
                font-weight: 900;
                background: rgba(8,12,18,220);
                border-radius: 7px;
                padding: 7px 10px;
            }
            QLabel#Capture {
                color: #9ec5ff;
                font-size: 11px;
                font-weight: 900;
                background: rgba(8,12,18,240);
                border: 1px solid rgba(76,134,234,190);
                border-radius: 8px;
                padding: 7px 12px;
            }
            QPushButton#OverlayTool {
                color: white;
                background: rgba(22,31,45,235);
                border: 1px solid rgba(100,120,150,190);
                border-radius: 8px;
                padding: 7px 11px;
                font-weight: 800;
            }
            QPushButton#OverlayDone {
                color: white;
                background: rgba(42,128,85,235);
                border: 1px solid rgba(120,240,170,210);
                border-radius: 8px;
                padding: 7px 11px;
                font-weight: 900;
            }
        """)

        self.toolbar = QWidget(self.root)
        bar = QHBoxLayout(self.toolbar)
        bar.setContentsMargins(8, 8, 8, 8)
        bar.setSpacing(6)

        title = QLabel("PHONEVIEW  •  MAPPING")
        title.setObjectName("OverlayTitle")
        bar.addWidget(title)

        self.status = QLabel("EDIT MODE")
        self.status.setObjectName("OverlayTitle")
        bar.addWidget(self.status)

        self.add_button = QPushButton("＋ Add Button")
        self.add_button.setObjectName("OverlayTool")
        self.add_button.clicked.connect(self.begin_capture)
        bar.addWidget(self.add_button)

        self.done_button = QPushButton("✓ Done")
        self.done_button.setObjectName("OverlayDone")
        self.done_button.clicked.connect(self.finish_editing)
        bar.addWidget(self.done_button)

        self.capture_label = QLabel("")
        self.capture_label.setObjectName("Capture")
        self.capture_label.hide()
        bar.addWidget(self.capture_label)

        bar.addStretch(1)

        QApplication.instance().installEventFilter(self)
        self.rebuild_buttons()

    def _find_window_geometry(self):
        title = self.window_title.strip()
        if not title:
            return None

        try:
            result = subprocess.run(
                ["wmctrl", "-lG"],
                capture_output=True, text=True, timeout=1.5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split(None, 6)
                    if len(parts) >= 7 and parts[6].strip() == title:
                        return tuple(int(parts[i]) for i in range(2, 6))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", f"^{re.escape(title)}$"],
                capture_output=True, text=True, timeout=1.5
            )
            if result.returncode == 0:
                wid = result.stdout.strip().splitlines()[0]
                geo = subprocess.run(
                    ["xdotool", "getwindowgeometry", "--shell", wid],
                    capture_output=True, text=True, timeout=1.5
                )
                values = {}
                for line in geo.stdout.splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        values[key] = int(value)
                if all(k in values for k in ("X", "Y", "WIDTH", "HEIGHT")):
                    return values["X"], values["Y"], values["WIDTH"], values["HEIGHT"]
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            pass
        return None

    def sync_to_scrcpy(self):
        if not self.isVisible():
            return
        geometry = self._find_window_geometry()
        if not geometry:
            return
        x, y, w, h = geometry
        if w < 120 or h < 120:
            return
        self.setGeometry(x, y, w, h)
        self.root.setGeometry(0, 0, w, h)
        self.toolbar.adjustSize()
        self.toolbar.move(8, 8)
        for button in self.findChildren(MappingButton):
            item = button.item
            px = int(float(item.get("x", 0.45)) * max(1, w))
            py = int(float(item.get("y", 0.45)) * max(1, h))
            px = max(0, min(w - button.width(), px))
            py = max(0, min(h - button.height(), py))
            button.move(px, py)

    def show_editor(self):
        self.edit_mode = True
        self.show()
        self.raise_()
        self.sync_to_scrcpy()
        self.setFocus(Qt.OtherFocusReason)
        self.status.setText("EDIT MODE")
        self.capture_label.hide()

    def finish_editing(self):
        self.capture_mode = False
        self.edit_mode = False
        self.capture_label.hide()
        self.status.setText("VIEW MODE")
        self.changed.emit()
        self.hide()

    def begin_capture(self):
        self.capture_mode = True
        self.capture_label.setText(
            "Press a keyboard key OR click / wheel the mouse…   •   Esc = cancel"
        )
        self.capture_label.show()
        self.status.setText("WAITING FOR INPUT")
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

    def cancel_capture(self):
        self.capture_mode = False
        self.capture_label.hide()
        self.status.setText("EDIT MODE")
        self.setFocus(Qt.OtherFocusReason)

    @staticmethod
    def key_name(event):
        key = event.key()
        special = {
            Qt.Key_Space: "SPACE", Qt.Key_Return: "ENTER", Qt.Key_Enter: "ENTER",
            Qt.Key_Tab: "TAB", Qt.Key_Backspace: "BACKSPACE", Qt.Key_Delete: "DELETE",
            Qt.Key_Insert: "INSERT", Qt.Key_Escape: "ESC", Qt.Key_Shift: "SHIFT",
            Qt.Key_Control: "CTRL", Qt.Key_Alt: "ALT", Qt.Key_Meta: "META",
            Qt.Key_CapsLock: "CAPS LOCK", Qt.Key_NumLock: "NUM LOCK",
            Qt.Key_ScrollLock: "SCROLL LOCK", Qt.Key_Left: "LEFT", Qt.Key_Right: "RIGHT",
            Qt.Key_Up: "UP", Qt.Key_Down: "DOWN", Qt.Key_Home: "HOME", Qt.Key_End: "END",
            Qt.Key_PageUp: "PAGE UP", Qt.Key_PageDown: "PAGE DOWN",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3", Qt.Key_F4: "F4",
            Qt.Key_F5: "F5", Qt.Key_F6: "F6", Qt.Key_F7: "F7", Qt.Key_F8: "F8",
            Qt.Key_F9: "F9", Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
            Qt.Key_Print: "PRINT SCREEN", Qt.Key_Pause: "PAUSE", Qt.Key_Menu: "MENU",
        }
        if key in special:
            return special[key]
        text = event.text().strip()
        if text:
            return text.upper()
        if Qt.Key_A <= key <= Qt.Key_Z:
            return chr(ord("A") + key - Qt.Key_A)
        return QKeySequence(key).toString().upper() or f"KEY_{key}"

    def _capture_item(self, label, input_type, mouse_button=None):
        item = {
            "label": label[:18],
            "key": label,
            "type": input_type,
            "x": 0.45,
            "y": 0.45,
        }
        if mouse_button:
            item["mouse_button"] = mouse_button
        self.controls.append(item)
        self.capture_mode = False
        self.capture_label.hide()
        self.status.setText("EDIT MODE")
        self.rebuild_buttons()
        self.changed.emit()
        self.capture_finished.emit(item)

    @staticmethod
    def mouse_label(button):
        return {
            Qt.LeftButton: ("LMB", "left"),
            Qt.RightButton: ("RMB", "right"),
            Qt.MiddleButton: ("MMB", "middle"),
            Qt.XButton1: ("MOUSE 4", "x1"),
            Qt.XButton2: ("MOUSE 5", "x2"),
        }.get(button)

    @staticmethod
    def wheel_label(event):
        delta = event.angleDelta()
        if delta.y() > 0:
            return "WHEEL UP", "wheel_up"
        if delta.y() < 0:
            return "WHEEL DOWN", "wheel_down"
        if delta.x() > 0:
            return "WHEEL RIGHT", "wheel_right"
        if delta.x() < 0:
            return "WHEEL LEFT", "wheel_left"
        return None

    def eventFilter(self, watched, event):
        if self.capture_mode and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.cancel_capture()
                return True
            self._capture_item(self.key_name(event), "keyboard")
            return True

        if self.capture_mode and event.type() == QEvent.MouseButtonPress:
            if watched is self.add_button or watched is self.done_button:
                return False
            data = self.mouse_label(event.button())
            if data:
                self._capture_item(data[0], "mouse", mouse_button=data[1])
                return True

        if self.capture_mode and event.type() == QEvent.Wheel:
            data = self.wheel_label(event)
            if data:
                self._capture_item(data[0], "mouse", mouse_button=data[1])
                return True

        return super().eventFilter(watched, event)

    def rebuild_buttons(self):
        for button in self.findChildren(MappingButton):
            button.deleteLater()
        for item in self.controls:
            button = MappingButton(item, self.root)
            button.moved.connect(self._schedule_save)
            button.removed.connect(lambda item=item: self.remove_item(item))
            button.show()
        QTimer.singleShot(0, self.sync_to_scrcpy)

    def _schedule_save(self):
        self.changed.emit()

    def remove_item(self, item):
        try:
            self.controls.remove(item)
        except ValueError:
            return
        self.changed.emit()
        self.rebuild_buttons()

    def closeEvent(self, event):
        self.hide()
        event.ignore()

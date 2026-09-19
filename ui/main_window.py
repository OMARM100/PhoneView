import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QPoint, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import ADBManager
from core.scrcpy_manager import ScrcpyManager


QSS = """
QMainWindow, QWidget {
    background: #080B10;
    color: #F4F7FB;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QFrame#Header, QFrame#Sidebar, QFrame#Hero, QFrame#InfoCard, QFrame#Activity {
    background: #10151D;
    border: 1px solid #1E2733;
    border-radius: 18px;
}
QLabel#Brand { font-size: 25px; font-weight: 900; color: #FFFFFF; }
QLabel#Eyebrow { font-size: 9px; font-weight: 800; color: #6E9BFF; letter-spacing: 1px; }
QLabel#Title { font-size: 21px; font-weight: 900; color: #F7F9FC; }
QLabel#Subtitle, QLabel#Muted { font-size: 10px; color: #788596; }
QLabel#DeviceTitle { font-size: 18px; font-weight: 900; color: #FFFFFF; }
QLabel#HeroTitle { font-size: 22px; font-weight: 900; color: #F7F9FC; }
QLabel#HeroText { font-size: 10px; color: #8793A3; }
QLabel#StatusGood { color: #62E5A2; font-size: 10px; font-weight: 900; }
QLabel#StatusWarn { color: #F3C15E; font-size: 10px; font-weight: 900; }
QLabel#StatusBad { color: #FF7777; font-size: 10px; font-weight: 900; }

QFrame#DeviceRow {
    background: #0D1219;
    border: 1px solid #1D2632;
    border-radius: 13px;
}
QFrame#DeviceRow[selected="true"] {
    background: #14223A;
    border: 1px solid #356FBD;
}
QListWidget#Devices {
    background: transparent;
    border: none;
    outline: 0;
}
QListWidget#Devices::item { background: transparent; border: none; padding: 0; margin: 3px 0; }
QListWidget#Devices::item:selected { background: transparent; }

QFrame#PhoneStage {
    background: #070A0F;
    border: 1px solid #202A37;
    border-radius: 16px;
}
QFrame#MirrorHost {
    background: #020305;
    border: 1px solid #1D2632;
    border-radius: 13px;
}
QFrame#ControlPanel {
    background: #0B1017;
    border: 1px solid #202A37;
    border-radius: 13px;
}
QLabel#PhoneGlyph {
    color: #5D8EFF;
    font-size: 58px;
    font-weight: 900;
}
QLabel#StageState { color: #AAB5C4; font-size: 10px; font-weight: 800; }
QLabel#StageHint { color: #647184; font-size: 9px; }

QPushButton {
    min-height: 38px;
    padding: 0 15px;
    border-radius: 10px;
    border: 1px solid #293443;
    background: #171D26;
    color: #CAD3DE;
    font-size: 10px;
    font-weight: 850;
}
QPushButton:hover { background: #222B37; color: #FFFFFF; border-color: #3A4656; }
QPushButton:disabled { background: #12171E; color: #505C6C; border-color: #202833; }
QPushButton#Primary {
    background: #2D73E5;
    border-color: #2D73E5;
    color: #FFFFFF;
    min-width: 145px;
}
QPushButton#Primary:hover { background: #3C82F0; border-color: #3C82F0; }
QPushButton#Danger { color: #FF9292; }
QPushButton#Control, QPushButton#ControlAccent {
    min-height: 32px;
    min-width: 54px;
    padding: 0 8px;
    font-size: 9px;
    border-radius: 8px;
}
QPushButton#ControlDelete {
    min-height: 32px;
    min-width: 28px;
    max-width: 28px;
    padding: 0;
    color: #FF7777;
    background: #241316;
    border-color: #4B252A;
}
QPushButton#ControlAccent {
    background: #172B4A;
    border-color: #315E99;
    color: #8DB8FF;
}
QLineEdit {
    background: #0B1017;
    border: 1px solid #293443;
    border-radius: 9px;
    padding: 8px 10px;
    color: #FFFFFF;
}

QProgressBar {
    background: #090D13;
    border: none;
    border-radius: 4px;
    min-height: 7px;
    max-height: 7px;
}
QProgressBar::chunk { background: #4C86EA; border-radius: 4px; }

QTextEdit#Log {
    background: #090C11;
    border: none;
    color: #9AA7B8;
    padding: 10px;
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 9px;
}
"""


class DeviceRow(QFrame):
    def __init__(self, device):
        super().__init__()
        self.setObjectName("DeviceRow")
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        dot = QLabel("●")
        dot.setFixedWidth(12)
        dot.setAlignment(Qt.AlignCenter)
        dot.setStyleSheet(
            "color:#62E5A2;" if device.state == "device"
            else "color:#F3C15E;" if device.state == "unauthorized"
            else "color:#FF7777;"
        )
        layout.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(2)

        name = QLabel(device.model or device.product or "Android phone")
        name.setObjectName("DeviceTitle")
        name.setStyleSheet("font-size:11px;")
        text.addWidget(name)

        meta = QLabel(device.serial)
        meta.setObjectName("Muted")
        text.addWidget(meta)
        layout.addLayout(text, 1)

        state = QLabel(
            "READY" if device.state == "device"
            else "AUTHORIZE" if device.state == "unauthorized"
            else device.state.upper()
        )
        state.setObjectName(
            "StatusGood" if device.state == "device"
            else "StatusWarn" if device.state == "unauthorized"
            else "StatusBad"
        )
        layout.addWidget(state)


class MappingEditor(QWidget):
    mappingChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MappingEditor")
        self.mappings = []
        self.selected_index = -1
        self.dragging = False
        self.drag_offset = QPoint()
        self.setMinimumSize(420, 560)

    def set_mappings(self, mappings):
        self.mappings = [dict(x) for x in mappings]
        self.update()

    def _rect_for(self, item):
        w=max(48,int(self.width()*float(item.get("w",0.12))))
        h=max(34,int(self.height()*float(item.get("h",0.07))))
        x=int(self.width()*float(item.get("x",0.5))-w/2)
        y=int(self.height()*float(item.get("y",0.5))-h/2)
        return QRect(x,y,w,h)

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor("#05070A"))
        side=min(self.width()-28,int((self.height()-28)*9/16)); ph=int(side*16/9)
        phone=QRect((self.width()-side)//2,(self.height()-ph)//2,side,ph)
        p.setBrush(QColor("#101722")); p.setPen(QPen(QColor("#2A3A50"),2)); p.drawRoundedRect(phone,18,18)
        p.setPen(QColor("#66758A")); p.drawText(phone,Qt.AlignCenter,"ANDROID SCREEN PREVIEW\n\nDrag controls here")
        for i,item in enumerate(self.mappings):
            rect=self._rect_for(item); selected=i==self.selected_index
            p.setBrush(QColor(45,115,229,215 if selected else 145))
            p.setPen(QPen(QColor("#8DB8FF") if selected else QColor("#385A87"),2))
            p.drawRoundedRect(rect,9,9); p.setPen(QColor("#FFFFFF"))
            p.drawText(rect,Qt.AlignCenter,str(item.get("label","KEY"))[:16])
        p.setPen(QColor("#66758A")); p.drawText(12,self.height()-12,"EDIT MODE  •  Drag controls  •  Double-click to edit")

    def _hit(self,pos):
        for i in range(len(self.mappings)-1,-1,-1):
            if self._rect_for(self.mappings[i]).contains(pos): return i
        return -1

    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton: return
        self.selected_index=self._hit(event.position().toPoint())
        self.dragging=self.selected_index>=0
        if self.dragging:
            self.drag_offset=event.position().toPoint()-self._rect_for(self.mappings[self.selected_index]).center()
        self.update()

    def mouseMoveEvent(self,event):
        if not self.dragging or self.selected_index<0: return
        pos=event.position().toPoint()-self.drag_offset; item=self.mappings[self.selected_index]
        item["x"]=max(0.08,min(0.92,pos.x()/max(1,self.width())))
        item["y"]=max(0.06,min(0.94,pos.y()/max(1,self.height())))
        self.mappingChanged.emit(); self.update()

    def mouseReleaseEvent(self,event):
        self.dragging=False

    def mouseDoubleClickEvent(self,event):
        i=self._hit(event.position().toPoint())
        if i<0: return
        item=self.mappings[i]
        label,ok=QInputDialog.getText(self,"Edit Mapping","Button label:",text=str(item.get("label","KEY")))
        if not ok or not label.strip(): return
        key,ok=QInputDialog.getText(self,"Keyboard Mapping","Keyboard key:",text=str(item.get("key","A")))
        if ok and key.strip():
            item["label"]=label.strip()[:16]; item["key"]=key.strip()[:32]
            self.mappingChanged.emit(); self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView")
        self.resize(1180, 760)
        self.setMinimumSize(920, 650)
        self.setStyleSheet(QSS)

        self.adb = ADBManager()
        self.scrcpy = ScrcpyManager()
        self.devices = []
        self.connected_serial = None
        self.refresh_in_progress = False
        self.project_name = "Android Project"
        self.controls_edit_mode = False
        self.control_buttons = []
        self.custom_controls = self.load_custom_controls()

        self.build_ui()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_devices)
        self.refresh_timer.start(2500)

        self.stream_timer = QTimer(self)
        self.stream_timer.timeout.connect(self.check_stream)
        self.stream_timer.start(500)

        QTimer.singleShot(120, self.refresh_devices)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(18, 16, 18, 16)
        main.setSpacing(12)

        header = QFrame()
        header.setObjectName("Header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 14, 20, 14)
        hl.setSpacing(16)

        brand = QVBoxLayout()
        brand.setSpacing(1)
        b = QLabel("PhoneView")
        b.setObjectName("Brand")
        brand.addWidget(b)
        sub = QLabel("ANDROID CONTROL CENTER")
        sub.setObjectName("Eyebrow")
        brand.addWidget(sub)
        hl.addLayout(brand)

        hl.addStretch()

        self.header_state = QLabel("●  NO DEVICE")
        self.header_state.setObjectName("StatusWarn")
        hl.addWidget(self.header_state)

        self.project_input = QLineEdit("Android Project")
        self.project_input.setPlaceholderText("Project name")
        self.project_input.setToolTip("This name becomes the title of the Android mirror window.")
        self.project_input.setMaximumWidth(190)
        self.project_input.textChanged.connect(self.set_project_name)
        hl.addWidget(self.project_input)

        self.refresh_button = QPushButton("↻  Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        hl.addWidget(self.refresh_button)

        main.addWidget(header)

        content = QHBoxLayout()
        content.setSpacing(12)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(14, 14, 14, 14)
        sl.setSpacing(9)

        top = QHBoxLayout()
        title = QLabel("Devices")
        title.setObjectName("Title")
        top.addWidget(title)
        top.addStretch()
        self.device_count = QLabel("0")
        self.device_count.setObjectName("Muted")
        top.addWidget(self.device_count)
        sl.addLayout(top)

        self.device_list = QListWidget()
        self.device_list.setObjectName("Devices")
        self.device_list.setMinimumWidth(300)
        self.device_list.itemSelectionChanged.connect(self.on_device_selected)
        sl.addWidget(self.device_list, 1)

        hint = QLabel("USB debugging enabled\n• unlock your phone\n• accept the ADB prompt")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        sl.addWidget(hint)
        content.addWidget(sidebar, 0)

        center = QVBoxLayout()
        center.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("Hero")
        hero_l = QVBoxLayout(hero)
        hero_l.setContentsMargins(18, 16, 18, 16)
        hero_l.setSpacing(10)

        hero_top = QHBoxLayout()
        hero_title_box = QVBoxLayout()
        hero_title_box.setSpacing(2)
        self.device_name = QLabel("No device selected")
        self.device_name.setObjectName("HeroTitle")
        hero_title_box.addWidget(self.device_name)
        self.device_meta = QLabel("Connect an Android phone to begin.")
        self.device_meta.setObjectName("HeroText")
        self.device_meta.setWordWrap(True)
        hero_title_box.addWidget(self.device_meta)
        hero_top.addLayout(hero_title_box, 1)

        self.stream_state = QLabel("●  OFFLINE")
        self.stream_state.setObjectName("StatusWarn")
        hero_top.addWidget(self.stream_state, 0, Qt.AlignTop)
        hero_l.addLayout(hero_top)

        stage = QFrame()
        stage.setObjectName("PhoneStage")
        stage_l = QHBoxLayout(stage)
        stage_l.setContentsMargins(10, 10, 10, 10)
        stage_l.setSpacing(10)

        self.mirror_host = QFrame()
        self.mirror_host.setObjectName("MirrorHost")
        mirror_l = QVBoxLayout(self.mirror_host)
        mirror_l.setContentsMargins(2, 2, 2, 2)
        mirror_l.setSpacing(0)
        self.mirror_placeholder = QLabel("MAPPING EDITOR\\n\\nPlace controls over the phone preview.\\nThe real Android screen stays in a separate scrcpy window.")
        self.mirror_placeholder.setObjectName("StageHint")
        self.mirror_placeholder.setAlignment(Qt.AlignCenter)
        mirror_l.addWidget(self.mirror_placeholder, 1)
        stage_l.addWidget(self.mirror_host, 1)

        controls = QFrame()
        controls.setObjectName("ControlPanel")
        controls.setFixedWidth(176)
        self.control_panel_layout = QVBoxLayout(controls)
        self.control_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.control_panel_layout.setSpacing(6)

        title = QLabel("PHONE CONTROLS")
        title.setObjectName("Eyebrow")
        title.setAlignment(Qt.AlignCenter)
        self.control_panel_layout.addWidget(title)

        self.control_state = QLabel("Editor mode\\nScrcpy stays separate")
        self.control_state.setObjectName("Muted")
        self.control_state.setAlignment(Qt.AlignCenter)
        self.control_panel_layout.addWidget(self.control_state)

        self.controls_container = QFrame()
        self.controls_container.setObjectName("ControlsContainer")
        self.controls_layout = QVBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(5)
        self.control_panel_layout.addWidget(self.controls_container, 1)

        add_button = QPushButton("＋  Add Button")
        add_button.setObjectName("ControlAccent")
        add_button.clicked.connect(self.add_custom_control)
        self.control_panel_layout.addWidget(add_button)

        self.edit_controls_button = QPushButton("✎  Edit Buttons")
        self.edit_controls_button.setObjectName("Control")
        self.edit_controls_button.clicked.connect(self.toggle_controls_edit)
        self.control_panel_layout.addWidget(self.edit_controls_button)

        focus = QPushButton("Focus Screen")
        focus.setObjectName("ControlAccent")
        focus.clicked.connect(self.focus_scrcpy)
        self.control_panel_layout.addWidget(focus)

        stage_l.addWidget(controls)
        self.mapping_editor = MappingEditor()
        self.mapping_editor.set_mappings(self.custom_controls)
        self.mapping_editor.hide()
        mirror_l.addWidget(self.mapping_editor, 1)
        self.rebuild_controls()
        hero_l.addWidget(stage, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        hero_l.addWidget(self.progress)

        actions = QHBoxLayout()
        self.connect_button = QPushButton("Connect & View")
        self.connect_button.setObjectName("Primary")
        self.connect_button.clicked.connect(self.connect_selected)
        actions.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("Danger")
        self.disconnect_button.clicked.connect(self.disconnect)
        actions.addWidget(self.disconnect_button)
        actions.addStretch()
        hero_l.addLayout(actions)
        center.addWidget(hero, 1)

        cards = QHBoxLayout()
        cards.setSpacing(12)

        info = QFrame()
        info.setObjectName("InfoCard")
        il = QVBoxLayout(info)
        il.setContentsMargins(16, 13, 16, 13)
        il.setSpacing(6)
        il.addWidget(QLabel("DEVICE DETAILS", objectName="Eyebrow"))
        self.info_text = QLabel("No device information yet.")
        self.info_text.setObjectName("HeroText")
        self.info_text.setWordWrap(True)
        il.addWidget(self.info_text)
        cards.addWidget(info, 1)

        engine = QFrame()
        engine.setObjectName("InfoCard")
        el = QVBoxLayout(engine)
        el.setContentsMargins(16, 13, 16, 13)
        el.setSpacing(6)
        el.addWidget(QLabel("SCREEN ENGINE", objectName="Eyebrow"))
        self.engine_text = QLabel("scrcpy not detected")
        self.engine_text.setObjectName("HeroText")
        self.engine_text.setWordWrap(True)
        el.addWidget(self.engine_text)
        cards.addWidget(engine, 1)
        center.addLayout(cards)

        content.addLayout(center, 1)
        main.addLayout(content, 1)

        activity = QFrame()
        activity.setObjectName("Activity")
        al = QVBoxLayout(activity)
        al.setContentsMargins(14, 11, 14, 11)
        al.setSpacing(7)

        ah = QHBoxLayout()
        ah.addWidget(QLabel("Live activity", objectName="Title"))
        ah.addStretch()
        ah.addWidget(QLabel("REAL-TIME", objectName="Eyebrow"))
        al.addLayout(ah)

        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(96)
        al.addWidget(self.log)
        main.addWidget(activity)

        self.write_log("PhoneView started. Android mirror stays in a separate scrcpy window.")
        if not self.adb.available():
            self.write_log("✗ ADB was not found.")
        if not self.scrcpy.available():
            self.write_log("✗ scrcpy was not found.")
        elif self.scrcpy.is_legacy():
            self.write_log("! Legacy scrcpy detected: " + self.scrcpy.version())
            self.write_log("! Update scrcpy before starting screen mirroring.")
        self.engine_text.setText(self.scrcpy.version() or "scrcpy not detected")
        self.update_buttons()

    def set_project_name(self, name):
        clean = " ".join(name.split()).strip()
        self.project_name = clean[:80] or "Android Project"

    def write_log(self, message):
        self.log.append(message)

    def refresh_devices(self):
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        try:
            if not self.adb.available():
                self.status_label_fallback("ADB is not installed or available in PATH.")
                self.header_state.setText("●  ADB UNAVAILABLE")
                return

            ok, error = self.adb.start_server()
            if not ok:
                self.status_label_fallback("ADB server could not start.")
                self.header_state.setText("●  ADB ERROR")
                self.write_log(f"✗ ADB server: {error}")
                return

            devices = self.adb.devices()
            previous = self.device_list.currentItem().data(Qt.UserRole) if self.device_list.currentItem() else None
            self.devices = devices

            self.device_list.blockSignals(True)
            self.device_list.clear()
            selected_row = -1

            for index, device in enumerate(devices):
                item = QListWidgetItem()
                item.setData(Qt.UserRole, device.serial)
                row = DeviceRow(device)
                item.setSizeHint(row.sizeHint())
                self.device_list.addItem(item)
                self.device_list.setItemWidget(item, row)
                if device.serial == previous:
                    selected_row = index

            if devices:
                self.device_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
            self.device_list.blockSignals(False)

            count = len(devices)
            self.device_count.setText(f"{count} connected")

            if not devices:
                self.header_state.setText("●  NO DEVICE")
                self.device_name.setText("No device selected")
                self.device_meta.setText("Connect an Android phone with USB debugging enabled.")
                self.info_text.setText("No device information yet.")
                self.mirror_placeholder.setText("▯\n\nWAITING FOR PHONE\n\nConnect USB • unlock phone • accept the ADB prompt")
                self.update_buttons()
                return

            selected = self.current_device()
            if selected:
                self.update_device_card(selected)
        finally:
            self.refresh_in_progress = False

    def current_device(self):
        item = self.device_list.currentItem()
        if not item:
            return None
        serial = item.data(Qt.UserRole)
        return next((d for d in self.devices if d.serial == serial), None)

    def on_device_selected(self):
        device = self.current_device()
        if not device:
            return
        self.update_device_card(device)

        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            row = self.device_list.itemWidget(item)
            if row:
                row.setProperty("selected", item is self.device_list.currentItem())
                row.style().unpolish(row)
                row.style().polish(row)

    def update_device_card(self, device):
        model = device.model or device.product or "Android phone"
        self.device_name.setText(model)
        self.device_meta.setText(f"Serial: {device.serial}  •  ADB: {device.state}")

        if device.state == "device":
            self.header_state.setText("●  DEVICE READY")
            self.stream_state.setText("●  READY")
            self.stream_state.setObjectName("StatusGood")
            self.mirror_placeholder.setText("▯\n\nPHONE SCREEN\n\nClick Connect & View to start the embedded Android screen.")
        elif device.state == "unauthorized":
            self.header_state.setText("●  AUTHORIZE PHONE")
            self.stream_state.setText("●  AUTHORIZATION REQUIRED")
            self.stream_state.setObjectName("StatusWarn")
            self.mirror_placeholder.setText("▯\n\nUSB AUTHORIZATION REQUIRED\n\nUnlock the phone and accept the USB debugging dialog.")
        else:
            self.header_state.setText(f"●  {device.state.upper()}")
            self.stream_state.setText(f"●  {device.state.upper()}")
            self.stream_state.setObjectName("StatusBad")
            self.mirror_placeholder.setText(f"▯\n\nADB DEVICE NOT READY\n\nADB reports: {device.state}")

        self.update_buttons()

    def status_label_fallback(self, text):
        self.mirror_placeholder.setText(f"▯\n\n{text}")

    def update_buttons(self):
        device = self.current_device()
        ready = bool(device and device.state == "device")
        legacy = self.scrcpy.is_legacy()
        self.connect_button.setEnabled(ready and self.scrcpy.available() and not legacy and not self.scrcpy.running())
        self.disconnect_button.setEnabled(self.scrcpy.running())
        for button in self.findChildren(QPushButton):
            if button.objectName() in ("Control", "ControlAccent"):
                button.setEnabled(ready and self.scrcpy.running())

    def connect_selected(self):
        device = self.current_device()
        if not device:
            QMessageBox.information(self, "PhoneView", "Select an Android phone first.")
            return

        if device.state != "device":
            QMessageBox.warning(
                self,
                "PhoneView",
                "Unlock the phone and finish USB debugging authorization first."
                if device.state == "unauthorized"
                else f"ADB reports: {device.state}",
            )
            return

        if not self.scrcpy.available():
            QMessageBox.critical(self, "PhoneView", "scrcpy is not installed.")
            return

        if self.scrcpy.is_legacy():
            message = (
                self.scrcpy.compatibility_message()
                + "\n\nThe setup screen will update scrcpy automatically when the Linux package is available."
            )
            self.write_log("✗ " + message.replace("\n\n", " "))
            QMessageBox.warning(self, "scrcpy update required", message)
            return

        serial = device.serial
        self.connect_button.setEnabled(False)
        self.progress.setVisible(True)
        self.mirror_placeholder.setText("OPENING ANDROID SCREEN...\n\nThe scrcpy window will stay separate.")
        self.stream_state.setText("●  CONNECTING")
        self.stream_state.setObjectName("StatusWarn")
        self.header_state.setText("●  CONNECTING")
        self.write_log(f"Connecting to {serial}…")

        try:
            info = self.adb.device_info(serial)
            model = info["model"] or device.model or "Android phone"
            android = info["android"] or "?"
            sdk = info["sdk"] or "?"
            self.device_name.setText(model)
            self.device_meta.setText(f"{info['brand'] or 'Android'}  •  Android {android}  •  SDK {sdk}")
            self.info_text.setText(
                f"Model: {model}\nBrand: {info['brand'] or 'Unknown'}\n"
                f"Android: {android}\nSDK: {sdk}\nSerial: {serial}"
            )

            self.scrcpy.start(serial, self.project_name)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy exited before the mirror window was created.")

            self.connected_serial = serial
            self.progress.setVisible(False)
            self.stream_state.setText("●  SCREEN LIVE • SEPARATE WINDOW")
            self.stream_state.setObjectName("StatusGood")
            self.mirror_placeholder.hide()
            self.mapping_editor.set_mappings(self.custom_controls)
            self.mapping_editor.show()
            self.control_state.setText("Editor ready\nScrcpy is separate")
            self.header_state.setText("●  CONNECTED")
            self.write_log("✓ Android screen connected in a separate scrcpy window.")
            self.write_log("✓ PhoneView mapping editor is ready.")
            self.write_log(f"✓ scrcpy: {self.scrcpy.version() or 'running'}")
        except Exception as exc:
            self.connected_serial = None
            self.progress.setVisible(False)
            self.stream_state.setText("●  SCREEN UNAVAILABLE")
            self.stream_state.setObjectName("StatusBad")
            self.mirror_placeholder.setText("MAPPING EDITOR\n\nMIRROR FAILED\n\nSee Live activity.")
            self.header_state.setText("●  CONNECTION ERROR")
            self.write_log(f"✗ Connection failed: {exc}")
            QMessageBox.critical(self, "PhoneView", f"scrcpy could not start:\n\n{exc}")
        finally:
            self.update_buttons()

    def load_custom_controls(self):
        path = Path.home() / ".config" / "PhoneView" / "controls.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def save_custom_controls(self):
        path = Path.home() / ".config" / "PhoneView" / "controls.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.custom_controls, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            self.write_log(f"! Could not save custom buttons: {exc}")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget:
                widget.deleteLater()
            elif child:
                self._clear_layout(child)

    def rebuild_controls(self):
        self._clear_layout(self.controls_layout)
        self.control_buttons = []

        defaults = [
            ("▲", 19), ("◀", 21), ("OK", 66), ("▶", 22), ("▼", 20),
            ("BACK", 4), ("HOME", 3), ("SPACE", 62), ("SHIFT", 59),
            ("CTRL", 113), ("E", 33), ("R", 46),
        ]

        for label, keycode in defaults:
            self._add_control_row(label, keycode, False, None)

        for index, item in enumerate(self.custom_controls):
            label = str(item.get("label", "Button"))[:18]
            try:
                keycode = int(item.get("keycode", 0))
            except (TypeError, ValueError):
                keycode = 0
            self._add_control_row(label, keycode, True, index)

        self.controls_layout.addStretch()

    def _add_control_row(self, label, keycode, is_custom, index):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)

        button = QPushButton(label)
        button.setObjectName(
            "ControlAccent"
            if label in {"▲", "◀", "OK", "▶", "▼"}
            else "Control"
        )
        button.setEnabled(self.scrcpy.running() and bool(self.connected_serial))
        button.clicked.connect(
            lambda checked=False, code=keycode, name=label: self.send_key(code, name)
        )
        row.addWidget(button, 1)
        self.control_buttons.append(button)

        if self.controls_edit_mode and is_custom:
            edit = QPushButton("✎")
            edit.setObjectName("Control")
            edit.setFixedWidth(28)
            edit.clicked.connect(
                lambda checked=False, idx=index: self.edit_custom_control(idx)
            )
            row.addWidget(edit)

            up = QPushButton("↑")
            up.setObjectName("Control")
            up.setFixedWidth(28)
            up.setEnabled(index > 0)
            up.clicked.connect(
                lambda checked=False, idx=index: self.move_custom_control(idx, -1)
            )
            row.addWidget(up)

            down = QPushButton("↓")
            down.setObjectName("Control")
            down.setFixedWidth(28)
            down.setEnabled(index < len(self.custom_controls) - 1)
            down.clicked.connect(
                lambda checked=False, idx=index: self.move_custom_control(idx, 1)
            )
            row.addWidget(down)

            remove = QPushButton("×")
            remove.setObjectName("ControlDelete")
            remove.setFixedWidth(28)
            remove.clicked.connect(
                lambda checked=False, idx=index: self.remove_custom_control(idx)
            )
            row.addWidget(remove)

        self.controls_layout.addLayout(row)

    def add_custom_control(self):
        label, ok = QInputDialog.getText(
            self, "Add Phone Button", "Button name:"
        )
        label = label.strip()
        if not ok or not label:
            return

        keycode, ok = QInputDialog.getInt(
            self, "Android KeyCode", "ADB keycode:", 66, 0, 300, 1
        )
        if not ok:
            return

        self.custom_controls.append({
            "label": label[:18],
            "keycode": keycode,
            "type": "android_keyevent",
            "x": 0.78,
            "y": 0.72,
            "w": 0.12,
            "h": 0.07,
        })
        self.save_custom_controls()
        self.mapping_editor.set_mappings(self.custom_controls)
        self.rebuild_controls()
        self.write_log(f"✓ Custom button added: {label} → KEYCODE_{keycode}")

    def edit_custom_control(self, index):
        if index < 0 or index >= len(self.custom_controls):
            return

        item = self.custom_controls[index]
        old_label = str(item.get("label", "Button"))
        try:
            old_keycode = int(item.get("keycode", 66))
        except (TypeError, ValueError):
            old_keycode = 66

        label, ok = QInputDialog.getText(
            self, "Edit Phone Button", "Button name:", text=old_label
        )
        label = label.strip()
        if not ok or not label:
            return

        keycode, ok = QInputDialog.getInt(
            self, "Edit Android KeyCode", "ADB keycode:",
            old_keycode, 0, 300, 1
        )
        if not ok:
            return

        self.custom_controls[index] = {
            "label": label[:18],
            "keycode": keycode,
        }
        self.save_custom_controls()
        self.mapping_editor.set_mappings(self.custom_controls)
        self.rebuild_controls()
        self.write_log(
            f"✓ Custom button updated: {label} → KEYCODE_{keycode}"
        )

    def move_custom_control(self, index, direction):
        new_index = index + direction
        if index < 0 or new_index < 0 or new_index >= len(self.custom_controls):
            return

        self.custom_controls[index], self.custom_controls[new_index] = (
            self.custom_controls[new_index],
            self.custom_controls[index],
        )
        self.save_custom_controls()
        self.mapping_editor.set_mappings(self.custom_controls)
        self.rebuild_controls()

    def remove_custom_control(self, index):
        if index < 0 or index >= len(self.custom_controls):
            return

        label = str(self.custom_controls[index].get("label", "Button"))
        self.custom_controls.pop(index)
        self.save_custom_controls()
        self.mapping_editor.set_mappings(self.custom_controls)
        self.rebuild_controls()
        self.write_log(f"✓ Custom button removed: {label}")

    def toggle_controls_edit(self):
        self.controls_edit_mode = not self.controls_edit_mode
        self.edit_controls_button.setText(
            "✓  Done Editing" if self.controls_edit_mode else "✎  Edit Buttons"
        )
        self.rebuild_controls()
        self.write_log(
            "✓ Button edit mode enabled. Edit, reorder, or remove custom buttons."
            if self.controls_edit_mode
            else "✓ Button edit mode disabled."
        )

    def focus_scrcpy(self):
        try:
            self.scrcpy.focus_window(self.project_name)
        except Exception:
            self.write_log("! Could not focus the separate scrcpy window.")

    def send_key(self, keycode, label):
        serial = self.connected_serial or (self.current_device().serial if self.current_device() else None)
        if not serial or not self.scrcpy.running():
            return
        try:
            self.scrcpy.adb_keyevent(serial, keycode)
            self.write_log(f"✓ {label} sent to Android.")
            self.focus_scrcpy()
        except Exception as exc:
            self.write_log(f"✗ {label}: {exc}")
    def check_stream(self):
        if self.connected_serial and not self.scrcpy.running():
            self.scrcpy.read_output()
            self.write_log("✗ scrcpy screen window closed or stopped.")
            if self.scrcpy.last_output:
                self.write_log(self.scrcpy.last_output[-2500:])
            self.connected_serial = None
            self.stream_state.setText("●  SCREEN STOPPED")
            self.stream_state.setObjectName("StatusWarn")
            self.mirror_placeholder.show()
            self.mapping_editor.hide()
            self.mirror_placeholder.setText("MAPPING EDITOR\n\nAndroid screen stopped. Connect & View to start again.")
            self.control_state.setText("Editor mode\nScrcpy stays separate")
            self.header_state.setText("●  NOT CONNECTED")
            self.update_buttons()

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.progress.setVisible(False)
        self.stream_state.setText("●  OFFLINE")
        self.stream_state.setObjectName("StatusWarn")
        self.mirror_placeholder.show()
        self.mirror_placeholder.setText("MAPPING EDITOR\n\nConnect & View to open the separate Android screen.")
        self.mapping_editor.hide()
        self.control_state.setText("Editor mode\nScrcpy stays separate")
        self.header_state.setText("●  NO STREAM")
        self.write_log("Disconnected.")
        self.update_buttons()

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

from PySide6.QtCore import QTimer, Qt
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
    QTextEdit,
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
    background: #0A0E14;
    border: 1px solid #202A37;
    border-radius: 16px;
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
        stage_l = QVBoxLayout(stage)
        stage_l.setContentsMargins(20, 24, 20, 24)
        stage_l.setSpacing(8)
        stage_l.setAlignment(Qt.AlignCenter)

        glyph = QLabel("▯")
        glyph.setObjectName("PhoneGlyph")
        glyph.setAlignment(Qt.AlignCenter)
        stage_l.addWidget(glyph)

        self.stage_state = QLabel("PHONE MIRROR READY")
        self.stage_state.setObjectName("StageState")
        self.stage_state.setAlignment(Qt.AlignCenter)
        stage_l.addWidget(self.stage_state)

        self.stage_hint = QLabel("The Android mirror opens in the scrcpy window.")
        self.stage_hint.setObjectName("StageHint")
        self.stage_hint.setAlignment(Qt.AlignCenter)
        stage_l.addWidget(self.stage_hint)

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

        self.write_log("PhoneView started.")
        if not self.adb.available():
            self.write_log("✗ ADB was not found.")
        if not self.scrcpy.available():
            self.write_log("✗ scrcpy was not found.")
        elif self.scrcpy.is_legacy():
            self.write_log("! Legacy scrcpy detected: " + self.scrcpy.version())
            self.write_log("! Update scrcpy before starting screen mirroring.")
        self.engine_text.setText(self.scrcpy.version() or "scrcpy not detected")
        self.update_buttons()

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
                self.stage_state.setText("WAITING FOR PHONE")
                self.stage_hint.setText("Connect USB • unlock phone • accept the ADB prompt")
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
            self.stage_state.setText("READY TO MIRROR")
            self.stage_hint.setText("Click Connect & View to open the live Android screen.")
        elif device.state == "unauthorized":
            self.header_state.setText("●  AUTHORIZE PHONE")
            self.stream_state.setText("●  AUTHORIZATION REQUIRED")
            self.stream_state.setObjectName("StatusWarn")
            self.stage_state.setText("USB AUTHORIZATION REQUIRED")
            self.stage_hint.setText("Unlock the phone and accept the USB debugging dialog.")
        else:
            self.header_state.setText(f"●  {device.state.upper()}")
            self.stream_state.setText(f"●  {device.state.upper()}")
            self.stream_state.setObjectName("StatusBad")
            self.stage_state.setText("ADB DEVICE NOT READY")
            self.stage_hint.setText(f"ADB reports: {device.state}")

        self.update_buttons()

    def status_label_fallback(self, text):
        self.stage_hint.setText(text)

    def update_buttons(self):
        device = self.current_device()
        ready = bool(device and device.state == "device")
        legacy = self.scrcpy.is_legacy()
        self.connect_button.setEnabled(ready and self.scrcpy.available() and not legacy and not self.scrcpy.running())
        self.disconnect_button.setEnabled(self.scrcpy.running())

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
        self.stage_state.setText("STARTING SCREEN...")
        self.stage_hint.setText("Launching scrcpy and waiting for the mirror window.")
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

            self.scrcpy.start(serial)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy exited before the mirror window was created.")

            self.connected_serial = serial
            self.progress.setVisible(False)
            self.stream_state.setText("●  SCREEN STREAMING")
            self.stream_state.setObjectName("StatusGood")
            self.stage_state.setText("SCREEN IS LIVE")
            self.stage_hint.setText("The Android screen is open in the scrcpy window.")
            self.header_state.setText("●  CONNECTED")
            self.write_log("✓ Android screen connected.")
            self.write_log(f"✓ scrcpy: {self.scrcpy.version() or 'running'}")
        except Exception as exc:
            self.connected_serial = None
            self.progress.setVisible(False)
            self.stream_state.setText("●  SCREEN UNAVAILABLE")
            self.stream_state.setObjectName("StatusBad")
            self.stage_state.setText("MIRROR FAILED")
            self.stage_hint.setText("The exact scrcpy error has been added to Live activity.")
            self.header_state.setText("●  CONNECTION ERROR")
            self.write_log(f"✗ Connection failed: {exc}")
            QMessageBox.critical(self, "PhoneView", f"scrcpy could not start:\n\n{exc}")
        finally:
            self.update_buttons()

    def check_stream(self):
        if self.connected_serial and not self.scrcpy.running():
            self.scrcpy.read_output()
            self.write_log("✗ scrcpy screen window closed or stopped.")
            if self.scrcpy.last_output:
                self.write_log(self.scrcpy.last_output[-2500:])
            self.connected_serial = None
            self.stream_state.setText("●  SCREEN STOPPED")
            self.stream_state.setObjectName("StatusWarn")
            self.stage_state.setText("SCREEN STOPPED")
            self.stage_hint.setText("The mirror process ended. Check Live activity for the exact error.")
            self.header_state.setText("●  NOT CONNECTED")
            self.update_buttons()

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.progress.setVisible(False)
        self.stream_state.setText("●  OFFLINE")
        self.stream_state.setObjectName("StatusWarn")
        self.stage_state.setText("PHONE MIRROR READY")
        self.stage_hint.setText("The Android mirror opens in the scrcpy window.")
        self.header_state.setText("●  NO STREAM")
        self.write_log("Disconnected.")
        self.update_buttons()

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

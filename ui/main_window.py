from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QProgressBar, QSplitter, QTextEdit, QVBoxLayout, QWidget
)

from core.adb_manager import ADBManager
from core.scrcpy_manager import ScrcpyManager


MAIN_QSS = """
QMainWindow, QWidget {
    background: #0b0d11;
    color: #eef2f7;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QFrame#TopBar, QFrame#Panel {
    background: #11151b;
    border: 1px solid #202732;
    border-radius: 16px;
}
QLabel#Logo { color:#ffffff; font-size:24px; font-weight:900; }
QLabel#Tagline { color:#778292; font-size:10px; }
QLabel#Status { color:#7d8999; font-size:10px; font-weight:800; }
QLabel#Title { color:#f4f7fb; font-size:15px; font-weight:850; }
QLabel#Muted { color:#758091; font-size:10px; }
QLabel#DeviceName { color:#f4f7fb; font-size:14px; font-weight:850; }
QLabel#DeviceMeta { color:#7e8998; font-size:9px; }
QLabel#BigState { color:#dce5ef; font-size:18px; font-weight:900; }
QLabel#StateGood { color:#5de39a; font-size:10px; font-weight:900; }
QLabel#StateWarn { color:#f3bd55; font-size:10px; font-weight:900; }
QLabel#StateBad { color:#ff7777; font-size:10px; font-weight:900; }

QListWidget#Devices {
    background:#0d1015; border:1px solid #202732; border-radius:12px;
    padding:5px; outline:0;
}
QListWidget#Devices::item { background:transparent; border:0; padding:0; margin:3px; }
QListWidget#Devices::item:selected { background:transparent; }

QFrame#DeviceRow {
    background:#131820; border:1px solid #202832; border-radius:11px;
}
QFrame#DeviceRow[selected="true"] {
    background:#172338; border:1px solid #376db8;
}

QPushButton {
    min-height:38px; padding:0 16px; border-radius:10px;
    border:1px solid #29313d; background:#181d25; color:#cbd3de;
    font-size:10px; font-weight:850;
}
QPushButton:hover { background:#222a35; color:#ffffff; }
QPushButton:disabled { color:#596474; background:#14181e; }
QPushButton#Primary { background:#2878e5; border-color:#2878e5; color:#fff; min-width:125px; }
QPushButton#Primary:hover { background:#3988f2; }
QPushButton#Danger { color:#ff9191; }

QProgressBar {
    background:#0b0e13; border:0; border-radius:4px; height:6px;
    text-align:center; color:transparent;
}
QProgressBar::chunk { background:#3b83e8; border-radius:4px; }

QTextEdit#Log {
    background:#090b0f; border:1px solid #202732; border-radius:11px;
    color:#aab4c1; padding:9px; font-family:"DejaVu Sans Mono",monospace; font-size:9px;
}
QSplitter::handle { background:#0b0d11; width:8px; }
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
            "color:#5de39a;" if device.state == "device"
            else "color:#f3bd55;" if device.state == "unauthorized"
            else "color:#ff7777;"
        )
        layout.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(2)
        model = QLabel(device.model or device.product or "Android phone")
        model.setObjectName("DeviceName")
        text.addWidget(model)
        serial = QLabel(device.serial)
        serial.setObjectName("DeviceMeta")
        text.addWidget(serial)
        layout.addLayout(text, 1)

        state = QLabel(
            "READY" if device.state == "device"
            else "AUTHORIZE" if device.state == "unauthorized"
            else device.state.upper()
        )
        state.setObjectName(
            "StateGood" if device.state == "device"
            else "StateWarn" if device.state == "unauthorized"
            else "StateBad"
        )
        layout.addWidget(state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView")
        self.resize(1080, 720)
        self.setMinimumSize(820, 600)
        self.setStyleSheet(MAIN_QSS)

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

        QTimer.singleShot(100, self.refresh_devices)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        top = QFrame()
        top.setObjectName("TopBar")
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(20, 15, 20, 15)

        brand = QVBoxLayout()
        brand.setSpacing(1)
        logo = QLabel("PhoneView")
        logo.setObjectName("Logo")
        brand.addWidget(logo)
        tagline = QLabel("Android screen & device manager")
        tagline.setObjectName("Tagline")
        brand.addWidget(tagline)
        top_l.addLayout(brand, 1)

        self.header_state = QLabel("●  NO DEVICE")
        self.header_state.setObjectName("Status")
        top_l.addWidget(self.header_state)
        layout.addWidget(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QFrame()
        left.setObjectName("Panel")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(15, 15, 15, 15)
        left_l.setSpacing(9)

        row = QHBoxLayout()
        title = QLabel("Devices")
        title.setObjectName("Title")
        row.addWidget(title)
        row.addStretch()
        self.device_count = QLabel("0 devices")
        self.device_count.setObjectName("Muted")
        row.addWidget(self.device_count)
        left_l.addLayout(row)

        self.device_list = QListWidget()
        self.device_list.setObjectName("Devices")
        self.device_list.setMinimumWidth(290)
        self.device_list.itemSelectionChanged.connect(self.on_device_selected)
        left_l.addWidget(self.device_list, 1)

        self.selection_hint = QLabel("Connect a phone with USB debugging enabled.")
        self.selection_hint.setObjectName("Muted")
        self.selection_hint.setWordWrap(True)
        left_l.addWidget(self.selection_hint)

        self.refresh_button = QPushButton("↻  Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        left_l.addWidget(self.refresh_button)
        splitter.addWidget(left)

        right = QFrame()
        right.setObjectName("Panel")
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(20, 18, 20, 18)
        right_l.setSpacing(10)

        right_l.addWidget(QLabel("SELECTED DEVICE", objectName="Muted"))
        self.device_name = QLabel("No device selected")
        self.device_name.setObjectName("BigState")
        right_l.addWidget(self.device_name)

        self.device_meta = QLabel("Waiting for Android device…")
        self.device_meta.setObjectName("DeviceMeta")
        self.device_meta.setWordWrap(True)
        right_l.addWidget(self.device_meta)

        self.stream_state = QLabel("NOT STREAMING")
        self.stream_state.setObjectName("StateWarn")
        right_l.addWidget(self.stream_state)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        right_l.addWidget(self.progress)

        self.status_label = QLabel("Waiting for a device.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        right_l.addWidget(self.status_label)

        right_l.addStretch()

        engine = QLabel(f"Screen engine  •  {self.scrcpy.version() or 'scrcpy not detected'}")
        engine.setObjectName("Muted")
        right_l.addWidget(engine)

        actions = QHBoxLayout()
        self.connect_button = QPushButton("Connect & View")
        self.connect_button.setObjectName("Primary")
        self.connect_button.clicked.connect(self.connect_selected)
        actions.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("Danger")
        self.disconnect_button.clicked.connect(self.disconnect)
        actions.addWidget(self.disconnect_button)
        right_l.addLayout(actions)

        splitter.addWidget(right)
        splitter.setSizes([330, 690])
        layout.addWidget(splitter, 1)

        log_header = QHBoxLayout()
        log_title = QLabel("Live activity")
        log_title.setObjectName("Title")
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(QLabel("REAL-TIME", objectName="Muted"))
        layout.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(105)
        layout.addWidget(self.log)

        self.write_log("PhoneView started.")
        if not self.adb.available():
            self.write_log("✗ ADB was not found.")
        if not self.scrcpy.available():
            self.write_log("✗ scrcpy was not found.")
        self.update_buttons()

    def write_log(self, message):
        self.log.append(message)

    def refresh_devices(self):
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        try:
            if not self.adb.available():
                self.status_label.setText("ADB is not installed or not available in PATH.")
                self.header_state.setText("●  ADB UNAVAILABLE")
                return

            ok, error = self.adb.start_server()
            if not ok:
                self.status_label.setText("ADB server could not start.")
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
            self.device_count.setText("1 device" if count == 1 else f"{count} devices")

            if not devices:
                self.header_state.setText("●  NO DEVICE")
                self.device_name.setText("No device selected")
                self.device_meta.setText("Connect an Android phone with USB.")
                self.status_label.setText("Enable Developer options → USB debugging, then unlock the phone.")
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
        self.device_meta.setText(f"Serial: {device.serial}\nADB state: {device.state}")

        if device.state == "device":
            self.header_state.setText("●  DEVICE READY")
            self.stream_state.setText("READY")
            self.stream_state.setObjectName("StateGood")
            self.status_label.setText("Phone is authorized and ready to mirror.")
            self.selection_hint.setText("Ready. Click Connect & View.")
        elif device.state == "unauthorized":
            self.header_state.setText("●  AUTHORIZE PHONE")
            self.stream_state.setText("AUTHORIZATION REQUIRED")
            self.stream_state.setObjectName("StateWarn")
            self.status_label.setText("Unlock the phone and accept the USB debugging prompt.")
            self.selection_hint.setText("Accept the authorization dialog on the phone.")
        else:
            self.header_state.setText(f"●  {device.state.upper()}")
            self.stream_state.setText(device.state.upper())
            self.status_label.setText(f"ADB reports this device as: {device.state}")
        self.update_buttons()

    def update_buttons(self):
        device = self.current_device()
        ready = bool(device and device.state == "device")
        self.connect_button.setEnabled(ready and not self.scrcpy.running())
        self.disconnect_button.setEnabled(self.scrcpy.running())

    def connect_selected(self):
        device = self.current_device()
        if not device:
            QMessageBox.information(self, "PhoneView", "Select an Android phone first.")
            return

        if device.state != "device":
            if device.state == "unauthorized":
                QMessageBox.warning(self, "USB authorization", "Unlock the phone and accept the USB debugging prompt, then refresh.")
            else:
                QMessageBox.warning(self, "PhoneView", f"ADB reports: {device.state}")
            return

        if not self.scrcpy.available():
            QMessageBox.critical(self, "PhoneView", "scrcpy is not installed or cannot be found.")
            return

        serial = device.serial
        self.connect_button.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Starting scrcpy…")
        self.stream_state.setText("STARTING SCREEN")
        self.stream_state.setObjectName("StateWarn")
        self.header_state.setText("●  CONNECTING")
        self.write_log(f"Connecting to {serial}…")

        try:
            info = self.adb.device_info(serial)
            model = info["model"] or device.model or "Android phone"
            self.device_name.setText(model)
            self.device_meta.setText(
                f"{info['brand'] or 'Android'}  •  Android {info['android'] or '?'}  •  SDK {info['sdk'] or '?'}\n"
                f"Serial: {serial}"
            )

            self.scrcpy.start(serial)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy exited before the mirror window was created.")

            self.connected_serial = serial
            self.progress.setVisible(False)
            self.stream_state.setText("●  SCREEN STREAMING")
            self.stream_state.setObjectName("StateGood")
            self.status_label.setText("Screen mirror is running.")
            self.header_state.setText("●  CONNECTED")
            self.write_log("✓ Android screen connected.")
            self.write_log(f"✓ scrcpy: {self.scrcpy.version() or 'running'}")
        except Exception as exc:
            self.connected_serial = None
            self.progress.setVisible(False)
            self.stream_state.setText("SCREEN NOT AVAILABLE")
            self.stream_state.setObjectName("StateBad")
            self.status_label.setText("scrcpy could not start. The real error is shown below.")
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
                self.write_log(self.scrcpy.last_output[-1800:])
            self.connected_serial = None
            self.stream_state.setText("SCREEN STOPPED")
            self.stream_state.setObjectName("StateWarn")
            self.header_state.setText("●  NOT CONNECTED")
            self.status_label.setText("The mirror process stopped. Check the activity log for the exact reason.")
            self.update_buttons()

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.progress.setVisible(False)
        self.stream_state.setText("NOT STREAMING")
        self.stream_state.setObjectName("StateWarn")
        self.header_state.setText("●  NO STREAM")
        self.status_label.setText("Android screen disconnected.")
        self.write_log("Disconnected.")
        self.update_buttons()

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

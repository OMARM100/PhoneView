from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import ADBManager
from core.scrcpy_manager import ScrcpyManager


MAIN_QSS = """
QMainWindow, QWidget {
    background: #0A0C0F;
    color: #E7EBF2;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QFrame#TopBar, QFrame#Panel {
    background: #111419;
    border: 1px solid #1D222A;
    border-radius: 14px;
}
QLabel#Brand {
    color: #F4F6FA;
    font-size: 21px;
    font-weight: 800;
}
QLabel#Subtitle {
    color: #707985;
    font-size: 9px;
}
QLabel#PanelTitle {
    color: #DDE3EB;
    font-size: 10px;
    font-weight: 800;
}
QLabel#Small {
    color: #707985;
    font-size: 9px;
}
QLabel#DeviceName {
    color: #F1F4F8;
    font-size: 15px;
    font-weight: 800;
}
QLabel#State {
    color: #78D69B;
    font-size: 9px;
    font-weight: 800;
}
QComboBox {
    background: #0D1014;
    border: 1px solid #252B34;
    border-radius: 9px;
    color: #E7EBF2;
    min-height: 42px;
    padding: 0 12px;
    font-size: 10px;
}
QComboBox:hover, QComboBox:on {
    border-color: #3C4756;
}
QComboBox::drop-down {
    width: 34px;
    border: none;
}
QComboBox QAbstractItemView {
    background: #111419;
    color: #E7EBF2;
    border: 1px solid #2A313B;
    selection-background-color: #1E4FA8;
    selection-color: #FFFFFF;
    outline: 0;
    padding: 5px;
}
QPushButton {
    min-height: 40px;
    padding: 0 13px;
    border-radius: 9px;
    border: 1px solid #262D36;
    background: #171B21;
    color: #BFC7D2;
    font-size: 9px;
    font-weight: 800;
}
QPushButton:hover {
    background: #1E242C;
    color: #FFFFFF;
    border-color: #39434F;
}
QPushButton#Primary {
    background: #2867D8;
    border-color: #2867D8;
    color: #FFFFFF;
    min-width: 126px;
}
QPushButton#Primary:hover {
    background: #3478EF;
}
QPushButton#Danger {
    color: #FF9B9B;
}
QTextEdit#Log {
    background: #0D1014;
    border: 1px solid #1D242D;
    border-radius: 10px;
    color: #AEB7C3;
    padding: 8px;
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 8px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView")
        self.resize(900, 610)
        self.setMinimumSize(700, 520)
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
        QTimer.singleShot(100, self.refresh_devices)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        top = QFrame()
        top.setObjectName("TopBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(18, 13, 18, 13)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        brand = QLabel("PhoneView")
        brand.setObjectName("Brand")
        brand_box.addWidget(brand)
        subtitle = QLabel("Android control center  •  USB / ADB")
        subtitle.setObjectName("Subtitle")
        brand_box.addWidget(subtitle)
        top_layout.addLayout(brand_box, 1)

        self.header_status = QLabel("●  Not connected")
        self.header_status.setObjectName("Small")
        self.header_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top_layout.addWidget(self.header_status)

        layout.addWidget(top)

        panel = QFrame()
        panel.setObjectName("Panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Android device")
        title.setObjectName("PanelTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.device_count = QLabel("No devices")
        self.device_count.setObjectName("Small")
        title_row.addWidget(self.device_count)
        panel_layout.addLayout(title_row)

        self.device_combo = QComboBox()
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.setMinimumHeight(44)
        self.device_combo.setPlaceholderText("No Android device detected")
        self.device_combo.currentIndexChanged.connect(self.on_device_selected)
        panel_layout.addWidget(self.device_combo)

        hint = QLabel("Select a phone above. Keep the phone unlocked and USB debugging enabled.")
        hint.setObjectName("Small")
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.refresh_button = QPushButton("Refresh devices")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("Primary")
        self.connect_button.clicked.connect(self.connect_selected)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("Danger")
        self.disconnect_button.clicked.connect(self.disconnect)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)
        actions.addWidget(self.connect_button)
        actions.addWidget(self.disconnect_button)
        panel_layout.addLayout(actions)

        self.status_label = QLabel("Waiting for a phone.")
        self.status_label.setObjectName("Small")
        self.status_label.setWordWrap(True)
        panel_layout.addWidget(self.status_label)

        layout.addWidget(panel)

        device = QFrame()
        device.setObjectName("Panel")
        device_layout = QVBoxLayout(device)
        device_layout.setContentsMargins(16, 14, 16, 14)
        device_layout.setSpacing(6)

        row = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        selected_title = QLabel("Selected device")
        selected_title.setObjectName("Small")
        left.addWidget(selected_title)
        self.device_label = QLabel("No device selected")
        self.device_label.setObjectName("DeviceName")
        self.device_label.setWordWrap(True)
        left.addWidget(self.device_label)
        row.addLayout(left, 1)

        self.stream_status = QLabel("NOT STREAMING")
        self.stream_status.setObjectName("State")
        row.addWidget(self.stream_status, 0, Qt.AlignTop)
        device_layout.addLayout(row)

        self.device_meta = QLabel("—")
        self.device_meta.setObjectName("Small")
        self.device_meta.setWordWrap(True)
        device_layout.addWidget(self.device_meta)

        layout.addWidget(device)

        log_title = QHBoxLayout()
        activity = QLabel("Activity")
        activity.setObjectName("PanelTitle")
        log_title.addWidget(activity)
        log_title.addStretch(1)
        log_hint = QLabel("CONNECTION EVENTS")
        log_hint.setObjectName("Small")
        log_title.addWidget(log_hint)
        layout.addLayout(log_title)

        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Connection events will appear here.")
        layout.addWidget(self.log, 1)

        self.write_log("PhoneView started.")
        if not self.adb.available():
            self.write_log("✗ ADB was not found.")
        if not self.scrcpy.available():
            self.write_log("✗ scrcpy was not found.")

    def write_log(self, message):
        self.log.append(message)

    def on_device_selected(self, index):
        if index < 0:
            return
        serial = self.device_combo.itemData(index)
        device = next((d for d in self.devices if d.serial == serial), None)
        if device:
            self.update_device_card(device)

    def refresh_devices(self):
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True

        try:
            if not self.adb.available():
                self.status_label.setText("ADB is not installed or is not available in PATH.")
                self.header_status.setText("●  ADB unavailable")
                return

            ok, error = self.adb.start_server()
            if not ok:
                self.status_label.setText("ADB server could not start.")
                self.header_status.setText("●  ADB error")
                self.write_log(f"✗ ADB server: {error}")
                return

            devices = self.adb.devices()
            previous = self.device_combo.currentData()
            self.devices = devices

            self.device_combo.blockSignals(True)
            self.device_combo.clear()

            for d in devices:
                model = d.model or d.product or "Android phone"
                if d.state == "device":
                    text = f"  {model}    •    Ready"
                elif d.state == "unauthorized":
                    text = f"  {model}    •    Authorization required"
                else:
                    text = f"  {model}    •    {d.state}"
                self.device_combo.addItem(text, d.serial)

            if previous:
                index = self.device_combo.findData(previous)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)
            elif devices:
                self.device_combo.setCurrentIndex(0)

            self.device_combo.blockSignals(False)

            count = len(devices)
            self.device_count.setText("1 device" if count == 1 else f"{count} devices")

            if not devices:
                self.device_label.setText("No device selected")
                self.device_meta.setText("Connect your Android phone with a USB cable.")
                self.status_label.setText(
                    "Waiting for a phone. Enable Developer options → USB debugging, then unlock the phone."
                )
                self.header_status.setText("●  Not connected")
                self.stream_status.setText("NOT STREAMING")
                return

            selected = next(
                (d for d in devices if d.serial == self.device_combo.currentData()),
                devices[0],
            )
            self.update_device_card(selected)

            if selected.state == "device":
                self.status_label.setText("Phone detected and ready to connect.")
                self.header_status.setText("●  Device ready")
            elif selected.state == "unauthorized":
                self.status_label.setText(
                    "USB debugging needs authorization. Unlock the phone and accept the RSA prompt."
                )
                self.header_status.setText("●  Authorization required")
            else:
                self.status_label.setText(f"ADB device state: {selected.state}")
                self.header_status.setText(f"●  {selected.state}")
        finally:
            self.refresh_in_progress = False

    def update_device_card(self, device):
        model = device.model or device.product or "Android phone"
        self.device_label.setText(model)
        self.device_meta.setText(
            f"Serial: {device.serial}   •   Connection: {device.state}"
        )

    def connect_selected(self):
        serial = self.device_combo.currentData()
        if not serial:
            QMessageBox.information(self, "PhoneView", "Select an Android phone first.")
            return

        device = next((d for d in self.devices if d.serial == serial), None)
        if not device:
            self.refresh_devices()
            return

        if device.state != "device":
            if device.state == "unauthorized":
                message = (
                    "Unlock the phone and accept the USB debugging authorization prompt.\n\n"
                    "Then press Refresh devices."
                )
            else:
                message = f"ADB reports this device as: {device.state}"
            QMessageBox.warning(self, "PhoneView", message)
            return

        if not self.scrcpy.available():
            QMessageBox.critical(self, "PhoneView", "scrcpy is not installed or cannot be found.")
            return

        self.connect_button.setEnabled(False)
        self.status_label.setText("Starting Android screen...")
        self.header_status.setText("●  Connecting")
        self.write_log(f"Connecting to {serial}...")

        try:
            info = self.adb.device_info(serial)
            model = info["model"] or device.model or "Android phone"
            brand = info["brand"] or ""
            android = info["android"] or "?"
            self.device_label.setText(model)
            self.device_meta.setText(
                f"{brand}   •   Android {android}   •   SDK {info['sdk'] or '?'}   •   {serial}"
            )

            self.scrcpy.start(serial)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy closed immediately after starting.")

            self.connected_serial = serial
            self.stream_status.setText("STREAMING")
            self.stream_status.setStyleSheet("color:#78D69B; font-weight:800;")
            self.status_label.setText("Android screen is open in the scrcpy window.")
            self.header_status.setText("●  Connected")
            self.write_log("✓ Android screen connected.")
        except Exception as exc:
            self.connected_serial = None
            self.stream_status.setText("NOT STREAMING")
            self.stream_status.setStyleSheet("")
            self.header_status.setText("●  Connection failed")
            self.status_label.setText("Could not start the Android screen.")
            self.write_log(f"✗ Connection failed: {exc}")
            QMessageBox.critical(self, "PhoneView", f"Connection failed:\n\n{exc}")
        finally:
            self.connect_button.setEnabled(True)

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.stream_status.setText("NOT STREAMING")
        self.stream_status.setStyleSheet("")
        self.header_status.setText("●  Not connected")
        self.status_label.setText("Android screen disconnected.")
        self.write_log("Disconnected.")

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

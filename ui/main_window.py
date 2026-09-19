from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
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
    background: #0B0D10;
    color: #E8EDF5;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QFrame#Header, QFrame#Card {
    background: #11151A;
    border: 1px solid #202832;
    border-radius: 16px;
}
QLabel#Eyebrow {
    color: #6E9BFF;
    font-size: 9px;
    font-weight: 800;
}
QLabel#Title {
    color: #F4F7FB;
    font-size: 25px;
    font-weight: 800;
}
QLabel#Subtitle, QLabel#Muted {
    color: #7F8998;
    font-size: 10px;
}
QLabel#Section {
    color: #DCE3ED;
    font-size: 11px;
    font-weight: 800;
}
QLabel#Status {
    color: #68D391;
    font-size: 10px;
    font-weight: 800;
}
QComboBox, QTextEdit {
    background: #0D1116;
    border: 1px solid #28313C;
    border-radius: 10px;
    color: #DCE3ED;
}
QComboBox {
    min-height: 38px;
    padding: 0 10px;
}
QComboBox:hover {
    border-color: #3B4858;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QTextEdit#Log {
    border-radius: 12px;
    padding: 8px;
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 9px;
}
QPushButton {
    min-height: 38px;
    padding: 0 14px;
    border-radius: 10px;
    border: 1px solid #2A333F;
    background: #171C22;
    color: #C8D0DB;
    font-size: 9px;
    font-weight: 800;
}
QPushButton:hover {
    background: #202731;
    border-color: #3A4655;
    color: #FFFFFF;
}
QPushButton#Primary {
    background: #2D6BEF;
    border-color: #2D6BEF;
    color: #FFFFFF;
    min-width: 132px;
}
QPushButton#Primary:hover {
    background: #4380FF;
}
QPushButton#Danger {
    color: #FF8D8D;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView")
        self.resize(900, 600)
        self.setMinimumSize(680, 500)
        self.setStyleSheet(MAIN_QSS)

        self.adb = ADBManager()
        self.scrcpy = ScrcpyManager()
        self.devices = []
        self.connected_serial = None
        self.refresh_in_progress = False

        self.build_ui()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_devices)
        self.refresh_timer.start(2000)

        QTimer.singleShot(100, self.refresh_devices)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        eyebrow = QLabel("PHONEVIEW  /  ANDROID")
        eyebrow.setObjectName("Eyebrow")
        title_box.addWidget(eyebrow)

        title = QLabel("PhoneView")
        title.setObjectName("Title")
        title_box.addWidget(title)

        subtitle = QLabel("USB / ADB connection and Android screen viewer")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box, 1)

        self.header_status = QLabel("●  Disconnected")
        self.header_status.setObjectName("Muted")
        self.header_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(self.header_status)

        layout.addWidget(header)

        connection = QFrame()
        connection.setObjectName("Card")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(14, 12, 14, 12)
        connection_layout.setSpacing(8)

        row_title = QHBoxLayout()
        section = QLabel("Device connection")
        section.setObjectName("Section")
        row_title.addWidget(section)
        row_title.addStretch(1)
        self.device_count = QLabel("0 devices")
        self.device_count.setObjectName("Muted")
        row_title.addWidget(self.device_count)
        connection_layout.addLayout(row_title)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.device_combo = QComboBox()
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.setPlaceholderText("Connect an Android phone with USB debugging enabled")

        self.refresh_button = QPushButton("↻  Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)

        self.connect_button = QPushButton("Connect / View")
        self.connect_button.setObjectName("Primary")
        self.connect_button.clicked.connect(self.connect_selected)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("Danger")
        self.disconnect_button.clicked.connect(self.disconnect)

        controls.addWidget(self.device_combo, 1)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.connect_button)
        controls.addWidget(self.disconnect_button)
        connection_layout.addLayout(controls)

        self.status_label = QLabel("Waiting for an Android device.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        connection_layout.addWidget(self.status_label)

        layout.addWidget(connection)

        device_card = QFrame()
        device_card.setObjectName("Card")
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(14, 12, 14, 12)
        device_layout.setSpacing(7)

        device_header = QHBoxLayout()
        device_title = QLabel("Selected device")
        device_title.setObjectName("Section")
        device_header.addWidget(device_title)
        device_header.addStretch(1)
        self.stream_status = QLabel("NOT STREAMING")
        self.stream_status.setObjectName("Muted")
        device_header.addWidget(self.stream_status)
        device_layout.addLayout(device_header)

        self.device_label = QLabel("No device selected")
        self.device_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #E8EDF5;")
        self.device_label.setWordWrap(True)
        device_layout.addWidget(self.device_label)

        self.device_meta = QLabel("—")
        self.device_meta.setObjectName("Muted")
        self.device_meta.setWordWrap(True)
        device_layout.addWidget(self.device_meta)

        layout.addWidget(device_card)

        log_header = QHBoxLayout()
        log_title = QLabel("Activity")
        log_title.setObjectName("Section")
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        log_hint = QLabel("LIVE CONNECTION LOG")
        log_hint.setObjectName("Muted")
        log_header.addWidget(log_hint)
        layout.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Connection activity will appear here...")
        layout.addWidget(self.log, 1)

        self.write_log("PhoneView started.")
        if not self.adb.available():
            self.write_log("✗ ADB was not found.")
        if not self.scrcpy.available():
            self.write_log("✗ scrcpy was not found.")

    def write_log(self, message):
        self.log.append(message)

    def refresh_devices(self):
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True

        try:
            if not self.adb.available():
                self.status_label.setText("ADB is not installed or not in PATH.")
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

            for device in devices:
                if device.state == "device":
                    label = device.model or device.product or "Android device"
                    text = f"{label}   •   {device.serial}"
                elif device.state == "unauthorized":
                    text = f"{device.serial}   •   USB authorization required"
                else:
                    text = f"{device.serial}   •   {device.state}"

                self.device_combo.addItem(text, device.serial)

            self.device_combo.blockSignals(False)

            if previous:
                index = self.device_combo.findData(previous)
                if index >= 0:
                    self.device_combo.setCurrentIndex(index)

            ready = [d for d in devices if d.state == "device"]
            self.device_count.setText(f"{len(devices)} device(s)")

            if not devices:
                self.status_label.setText(
                    "No Android device detected. Connect USB, enable USB debugging, then unlock the phone."
                )
                self.header_status.setText("●  Disconnected")
                if not self.scrcpy.running():
                    self.stream_status.setText("NOT STREAMING")
                return

            selected = next((d for d in devices if d.serial == self.device_combo.currentData()), devices[0])
            self.update_device_card(selected)

            if selected.state == "device":
                self.status_label.setText("Android device is ready.")
                self.header_status.setText("●  Device ready")
            elif selected.state == "unauthorized":
                self.status_label.setText(
                    "USB debugging authorization is required. Unlock the phone and accept the RSA prompt."
                )
                self.header_status.setText("●  Authorization needed")
            else:
                self.status_label.setText(f"ADB reports device state: {selected.state}")
                self.header_status.setText(f"●  {selected.state}")
        finally:
            self.refresh_in_progress = False

    def update_device_card(self, device):
        model = device.model or "Android"
        self.device_label.setText(model)
        self.device_meta.setText(
            f"Serial: {device.serial}    •    ADB state: {device.state}"
        )

    def connect_selected(self):
        serial = self.device_combo.currentData()
        if not serial:
            QMessageBox.information(
                self,
                "PhoneView",
                "Connect an Android device first.",
            )
            return

        device = next((d for d in self.devices if d.serial == serial), None)
        if not device:
            self.refresh_devices()
            return

        if device.state != "device":
            if device.state == "unauthorized":
                message = (
                    "The phone has not authorized USB debugging yet.\n\n"
                    "Unlock the phone and accept the RSA / USB debugging prompt, then press Refresh."
                )
            else:
                message = f"ADB reports the device state as: {device.state}"
            QMessageBox.warning(self, "PhoneView", message)
            return

        if not self.scrcpy.available():
            QMessageBox.critical(
                self,
                "PhoneView",
                "scrcpy is not installed or cannot be found in PATH.",
            )
            return

        self.connect_button.setEnabled(False)
        self.status_label.setText("Connecting to Android screen...")
        self.header_status.setText("●  Connecting...")
        self.write_log(f"Connecting to {serial}...")

        try:
            info = self.adb.device_info(serial)
            model = info["model"] or device.model or "Android"
            brand = info["brand"] or ""
            android = info["android"] or "?"
            self.device_label.setText(model)
            self.device_meta.setText(
                f"{brand}  •  Android {android}  •  SDK {info['sdk'] or '?'}  •  {serial}"
            )

            self.scrcpy.start(serial)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy started but the process is no longer running.")

            self.connected_serial = serial
            self.stream_status.setText("STREAMING")
            self.stream_status.setStyleSheet("color:#68D391; font-weight:800;")
            self.status_label.setText("Android screen is streaming in the scrcpy window.")
            self.header_status.setText("●  Connected")
            self.write_log("✓ Android screen connected successfully.")
        except Exception as exc:
            self.connected_serial = None
            self.stream_status.setText("NOT STREAMING")
            self.stream_status.setStyleSheet("")
            self.header_status.setText("●  Connection failed")
            self.status_label.setText("Could not start the Android screen stream.")
            self.write_log(f"✗ Connection failed: {exc}")
            QMessageBox.critical(self, "PhoneView", f"Connection failed:\n\n{exc}")
        finally:
            self.connect_button.setEnabled(True)

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.stream_status.setText("NOT STREAMING")
        self.stream_status.setStyleSheet("")
        self.header_status.setText("●  Disconnected")
        self.status_label.setText("Android screen disconnected.")
        self.write_log("Disconnected.")

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

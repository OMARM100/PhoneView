from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QGroupBox, QMessageBox
)
from core.adb_manager import ADBManager
from core.scrcpy_manager import ScrcpyManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView - USB")
        self.resize(760, 520)
        self.adb = ADBManager()
        self.scrcpy = ScrcpyManager()
        self.devices = []
        self.build_ui()
        self.refresh_devices()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_devices)
        self.timer.start(1500)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("PhoneView")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(title)
        subtitle = QLabel("Android screen viewer — USB / ADB")
        subtitle.setStyleSheet("color: #777;")
        layout.addWidget(subtitle)

        connection = QGroupBox("USB Connection")
        row = QHBoxLayout(connection)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(350)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.connect_button = QPushButton("Connect / View")
        self.connect_button.clicked.connect(self.connect_selected)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect)
        row.addWidget(self.device_combo)
        row.addWidget(self.refresh_button)
        row.addWidget(self.connect_button)
        row.addWidget(self.disconnect_button)
        layout.addWidget(connection)

        info = QGroupBox("Device")
        info_row = QVBoxLayout(info)
        self.device_label = QLabel("No device selected")
        self.status_label = QLabel("Status: Waiting for USB device")
        self.status_label.setStyleSheet("font-weight: bold;")
        info_row.addWidget(self.device_label)
        info_row.addWidget(self.status_label)
        layout.addWidget(info)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs...")
        layout.addWidget(self.log)
        self.write_log("PhoneView started.")

        if not self.adb.available():
            self.write_log("ADB was not found. Install Android Platform Tools and add adb to PATH.")
        if not self.scrcpy.available():
            self.write_log("scrcpy was not found. Install scrcpy and add it to PATH.")

    def write_log(self, message):
        self.log.append(message)

    def refresh_devices(self):
        if not self.adb.available():
            self.status_label.setText("Status: ADB not installed")
            return
        ok, _ = self.adb.start_server()
        if not ok:
            self.status_label.setText("Status: ADB error")
            return
        devices = self.adb.devices()
        previous = self.device_combo.currentData()
        self.devices = devices
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for d in devices:
            text = f"{d.model or 'Android'} — {d.serial}" if d.state == "device" else f"{d.serial} — {d.state}"
            self.device_combo.addItem(text, d.serial)
        self.device_combo.blockSignals(False)
        if previous:
            index = self.device_combo.findData(previous)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
        if not devices:
            self.device_label.setText("No Android device detected")
            self.status_label.setText("Status: Waiting for USB device")
        else:
            d = devices[self.device_combo.currentIndex()]
            self.device_label.setText(f"Model: {d.model or 'Unknown'}    Serial: {d.serial}")
            self.status_label.setText(f"Status: {d.state}")

    def connect_selected(self):
        serial = self.device_combo.currentData()
        if not serial:
            QMessageBox.warning(self, "PhoneView", "لا يوجد هاتف محدد.")
            return
        device = next((d for d in self.devices if d.serial == serial), None)
        if not device:
            return
        if device.state != "device":
            QMessageBox.warning(self, "PhoneView", "الهاتف غير مصرح له بالـ ADB. افتح شاشة الهاتف واقبل USB Debugging.")
            return
        try:
            info = self.adb.device_info(serial)
            self.device_label.setText(f"{info['brand']} {info['model']} — Android {info['android']}")
            self.scrcpy.start(serial)
            self.status_label.setText("Status: Connected / Streaming")
            self.write_log(f"Connected to {serial}")
        except Exception as e:
            self.write_log(f"Connection error: {e}")
            QMessageBox.critical(self, "PhoneView", str(e))

    def disconnect(self):
        self.scrcpy.stop()
        self.status_label.setText("Status: Disconnected")
        self.write_log("Disconnected.")

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

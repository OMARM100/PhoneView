from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.adb_manager import ADBManager
from core.scrcpy_manager import ScrcpyManager


MAIN_QSS = """
QMainWindow, QWidget {
    background: #0D0F12;
    color: #E9EDF3;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QFrame#Header, QFrame#Card {
    background: #17191D;
    border: 1px solid #292D34;
    border-radius: 14px;
}
QLabel#Eyebrow {
    color: #6E9FE8;
    font-size: 9px;
    font-weight: 800;
}
QLabel#Brand {
    color: #F5F7FA;
    font-size: 25px;
    font-weight: 900;
}
QLabel#Subtitle {
    color: #858D98;
    font-size: 10px;
}
QLabel#HeaderState {
    color: #7E8793;
    font-size: 9px;
    font-weight: 800;
}
QLabel#CardTitle {
    color: #F1F3F6;
    font-size: 13px;
    font-weight: 850;
}
QLabel#CardHint {
    color: #7E8793;
    font-size: 9px;
}
QLabel#DeviceName {
    color: #F3F5F8;
    font-size: 15px;
    font-weight: 850;
}
QLabel#DeviceMeta {
    color: #7E8793;
    font-size: 9px;
}
QLabel#Ready {
    color: #58CF86;
    font-size: 9px;
    font-weight: 850;
}
QLabel#Warning {
    color: #F0B84B;
    font-size: 9px;
    font-weight: 850;
}
QLabel#Error {
    color: #F47F7F;
    font-size: 9px;
    font-weight: 850;
}
QListWidget#Devices {
    background: #101216;
    border: 1px solid #272B32;
    border-radius: 10px;
    outline: 0;
    padding: 4px;
}
QListWidget#Devices::item {
    background: transparent;
    border: none;
    margin: 2px;
    padding: 0;
}
QListWidget#Devices::item:selected {
    background: transparent;
}
QFrame#DeviceRow {
    background: #14171B;
    border: 1px solid #252A31;
    border-radius: 9px;
}
QFrame#DeviceRow[selected="true"] {
    background: #172238;
    border: 1px solid #2D65B5;
}
QPushButton {
    min-height: 40px;
    padding: 0 14px;
    border-radius: 9px;
    border: 1px solid #2B3038;
    background: #1D2025;
    color: #C9CFD8;
    font-size: 9px;
    font-weight: 800;
}
QPushButton:hover {
    background: #262B32;
    color: #FFFFFF;
}
QPushButton:disabled {
    color: #5D6470;
    background: #17191D;
}
QPushButton#Primary {
    background: #2B70D9;
    border-color: #2B70D9;
    color: #FFFFFF;
    min-width: 118px;
}
QPushButton#Primary:hover {
    background: #367FEA;
}
QPushButton#Danger {
    color: #F28C8C;
}
QTextEdit#Log {
    background: #0A0C0F;
    border: 1px solid #252A31;
    border-radius: 9px;
    color: #AEB7C3;
    padding: 8px;
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 8px;
}
QSplitter::handle {
    background: #0D0F12;
    width: 8px;
}
"""


class DeviceRow(QFrame):
    def __init__(self, device):
        super().__init__()
        self.setObjectName("DeviceRow")
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        dot = QLabel("●")
        dot.setFixedWidth(13)
        dot.setAlignment(Qt.AlignCenter)
        dot.setStyleSheet(
            "color:#58CF86;" if device.state == "device"
            else "color:#F0B84B;" if device.state == "unauthorized"
            else "color:#F47F7F;"
        )
        layout.addWidget(dot)

        text = QVBoxLayout()
        text.setSpacing(1)

        model = QLabel(device.model or device.product or "Android phone")
        model.setObjectName("DeviceName")
        text.addWidget(model)

        serial = QLabel(device.serial)
        serial.setObjectName("DeviceMeta")
        text.addWidget(serial)

        layout.addLayout(text, 1)

        state = QLabel(
            "Ready" if device.state == "device"
            else "Authorization required" if device.state == "unauthorized"
            else device.state.title()
        )
        state.setObjectName(
            "Ready" if device.state == "device"
            else "Warning" if device.state == "unauthorized"
            else "Error"
        )
        state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(state)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhoneView")
        self.resize(980, 700)
        self.setMinimumSize(760, 560)
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
        self.stream_timer.start(700)

        QTimer.singleShot(100, self.refresh_devices)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)

        eyebrow = QLabel("ANDROID DESKTOP CLIENT")
        eyebrow.setObjectName("Eyebrow")
        brand_box.addWidget(eyebrow)

        brand = QLabel("PhoneView")
        brand.setObjectName("Brand")
        brand_box.addWidget(brand)

        subtitle = QLabel("Connect, view and control your Android device")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        brand_box.addWidget(subtitle)

        header_layout.addLayout(brand_box, 1)

        self.header_state = QLabel("●  NO DEVICE")
        self.header_state.setObjectName("HeaderState")
        self.header_state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(self.header_state)

        layout.addWidget(header)

        connection = QFrame()
        connection.setObjectName("Card")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(16, 15, 16, 15)
        connection_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Connect an Android device")
        title.setObjectName("CardTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)

        self.device_count = QLabel("0 devices")
        self.device_count.setObjectName("CardHint")
        title_row.addWidget(self.device_count)
        connection_layout.addLayout(title_row)

        self.device_list = QListWidget()
        self.device_list.setObjectName("Devices")
        self.device_list.setMinimumHeight(150)
        self.device_list.setSpacing(1)
        self.device_list.itemSelectionChanged.connect(self.on_device_selected)
        connection_layout.addWidget(self.device_list, 1)

        self.selection_hint = QLabel(
            "Unlock the phone and enable USB debugging. Select a device above to continue."
        )
        self.selection_hint.setObjectName("CardHint")
        self.selection_hint.setWordWrap(True)
        connection_layout.addWidget(self.selection_hint)

        layout.addWidget(connection, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        details = QFrame()
        details.setObjectName("Card")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(16, 15, 16, 15)
        details_layout.setSpacing(8)

        details_title = QLabel("Selected device")
        details_title.setObjectName("CardHint")
        details_layout.addWidget(details_title)

        self.device_name = QLabel("No device selected")
        self.device_name.setObjectName("DeviceName")
        self.device_name.setWordWrap(True)
        details_layout.addWidget(self.device_name)

        self.device_meta = QLabel("—")
        self.device_meta.setObjectName("DeviceMeta")
        self.device_meta.setWordWrap(True)
        details_layout.addWidget(self.device_meta)

        self.stream_state = QLabel("NOT STREAMING")
        self.stream_state.setObjectName("CardHint")
        details_layout.addWidget(self.stream_state)

        details_layout.addStretch(1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_devices)
        actions.addWidget(self.refresh_button)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("Primary")
        self.connect_button.clicked.connect(self.connect_selected)
        actions.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setObjectName("Danger")
        self.disconnect_button.clicked.connect(self.disconnect)
        actions.addWidget(self.disconnect_button)

        details_layout.addLayout(actions)
        splitter.addWidget(details)

        help_card = QFrame()
        help_card.setObjectName("Card")
        help_layout = QVBoxLayout(help_card)
        help_layout.setContentsMargins(16, 15, 16, 15)
        help_layout.setSpacing(7)

        help_title = QLabel("Connection")
        help_title.setObjectName("CardTitle")
        help_layout.addWidget(help_title)

        self.status_label = QLabel("Waiting for an Android device.")
        self.status_label.setObjectName("CardHint")
        self.status_label.setWordWrap(True)
        help_layout.addWidget(self.status_label)

        self.scrcpy_label = QLabel(
            f"Screen engine: {self.scrcpy.version() or 'scrcpy'}"
        )
        self.scrcpy_label.setObjectName("CardHint")
        self.scrcpy_label.setWordWrap(True)
        help_layout.addWidget(self.scrcpy_label)

        help_layout.addStretch(1)
        splitter.addWidget(help_card)

        splitter.setSizes([500, 380])
        layout.addWidget(splitter)

        log_header = QHBoxLayout()
        log_title = QLabel("Live activity")
        log_title.setObjectName("CardTitle")
        log_header.addWidget(log_title)
        log_header.addStretch(1)

        log_mode = QLabel("SYSTEM OUTPUT")
        log_mode.setObjectName("CardHint")
        log_header.addWidget(log_mode)
        layout.addLayout(log_header)

        self.log = QTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(90)
        layout.addWidget(self.log, 0)

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
                self.status_label.setText("ADB is not installed or is not available in PATH.")
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
                item.setSizeHint(DeviceRow(device).sizeHint())
                self.device_list.addItem(item)

                row = DeviceRow(device)
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
                self.status_label.setText(
                    "Waiting for a phone. Enable Developer options → USB debugging, then unlock the phone."
                )
                self.selection_hint.setText(
                    "No Android device detected. Connect the phone and press Refresh."
                )
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

        for index in range(self.device_list.count()):
            item = self.device_list.item(index)
            row = self.device_list.itemWidget(item)
            if row:
                row.setProperty("selected", item is self.device_list.currentItem())
                row.style().unpolish(row)
                row.style().polish(row)

    def update_device_card(self, device):
        model = device.model or device.product or "Android phone"
        self.device_name.setText(model)
        self.device_meta.setText(
            f"Serial: {device.serial}\nADB state: {device.state}"
        )

        if device.state == "device":
            self.header_state.setText("●  DEVICE READY")
            self.status_label.setText("Device is ready. Press Connect to start screen viewing.")
            self.selection_hint.setText("Ready. Press Connect to open the Android screen.")
        elif device.state == "unauthorized":
            self.header_state.setText("●  AUTHORIZATION")
            self.status_label.setText(
                "Unlock the phone and accept the USB debugging authorization dialog."
            )
            self.selection_hint.setText("Authorization is required on the Android device.")
        else:
            self.header_state.setText(f"●  {device.state.upper()}")
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
                QMessageBox.warning(
                    self,
                    "USB authorization",
                    "Unlock the phone and accept the USB debugging authorization prompt, then press Refresh.",
                )
            else:
                QMessageBox.warning(self, "PhoneView", f"ADB reports: {device.state}")
            return

        if not self.scrcpy.available():
            QMessageBox.critical(self, "PhoneView", "scrcpy is not installed or cannot be found.")
            return

        serial = device.serial
        self.connect_button.setEnabled(False)
        self.status_label.setText("Starting Android screen...")
        self.header_state.setText("●  CONNECTING")
        self.stream_state.setText("STARTING SCREEN")
        self.write_log(f"Connecting to {serial}...")

        try:
            info = self.adb.device_info(serial)
            model = info["model"] or device.model or "Android phone"
            self.device_name.setText(model)
            self.device_meta.setText(
                f"{info['brand'] or 'Android'}  •  Android {info['android'] or '?'}  •  "
                f"SDK {info['sdk'] or '?'}\nSerial: {serial}"
            )

            self.scrcpy.start(serial)

            if not self.scrcpy.running():
                raise RuntimeError("scrcpy exited before its screen window was created.")

            self.connected_serial = serial
            self.stream_state.setText("●  SCREEN STREAMING")
            self.stream_state.setStyleSheet("color:#58CF86; font-weight:850;")
            self.status_label.setText(
                "Screen window started. It should now be visible on the desktop."
            )
            self.header_state.setText("●  CONNECTED")
            self.write_log("✓ Android screen connected.")
        except Exception as exc:
            self.connected_serial = None
            self.stream_state.setText("SCREEN NOT AVAILABLE")
            self.stream_state.setStyleSheet("color:#F47F7F; font-weight:850;")
            self.header_state.setText("●  CONNECTION ERROR")
            self.status_label.setText("The Android screen could not be started.")
            self.write_log(f"✗ Connection failed: {exc}")
            QMessageBox.critical(self, "PhoneView", f"Connection failed:\n\n{exc}")
        finally:
            self.update_buttons()

    def check_stream(self):
        if self.connected_serial and not self.scrcpy.running():
            self.write_log("✗ scrcpy screen window closed or stopped.")
            if self.scrcpy.last_output:
                self.write_log(self.scrcpy.last_output[-1200:])
            self.connected_serial = None
            self.stream_state.setText("SCREEN STOPPED")
            self.stream_state.setStyleSheet("color:#F0B84B; font-weight:850;")
            self.header_state.setText("●  NOT CONNECTED")
            self.status_label.setText("The Android screen is no longer running.")
            self.update_buttons()

    def disconnect(self):
        self.scrcpy.stop()
        self.connected_serial = None
        self.stream_state.setText("NOT STREAMING")
        self.stream_state.setStyleSheet("")
        self.header_state.setText("●  NO STREAM")
        self.status_label.setText("Android screen disconnected.")
        self.write_log("Disconnected.")
        self.update_buttons()

    def closeEvent(self, event):
        self.scrcpy.stop()
        event.accept()

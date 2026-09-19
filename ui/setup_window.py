import re
import sys

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.dependency_checker import DependencyChecker


PHONEVIEW_QSS = """
QDialog {
    background: #121212;
    color: #E0E0E0;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}

QLabel {
    color: #E0E0E0;
    background: transparent;
}

QLabel#Eyebrow {
    color: #7D8AA0;
    font-size: 10px;
    font-weight: 700;
}

QLabel#Subtitle,
QLabel#Muted {
    color: #8D96A5;
}

QLabel#SectionTitle {
    color: #E0E0E0;
    font-size: 11px;
    font-weight: 700;
}

QLabel#StatusTitle {
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
}

QLabel#Percent {
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 700;
}

QFrame#Card {
    background: #1E1E1E;
    border: 1px solid #2A2A2A;
    border-radius: 14px;
}

QFrame#StatusCard {
    background: #1E1E1E;
    border: 1px solid #303030;
    border-radius: 16px;
}

QFrame#StatusAccent {
    background: #2979FF;
    border-radius: 3px;
}

QFrame#DependencyRow {
    background: #191919;
    border: 1px solid #292929;
    border-radius: 10px;
}

QFrame#DependencyRow:hover {
    background: #202020;
    border-color: #343434;
}

QLabel#DependencyName {
    color: #E0E0E0;
    font-size: 11px;
    font-weight: 600;
}

QLabel#DependencyState {
    color: #8D96A5;
    font-size: 10px;
    font-weight: 700;
}

QLabel#StatusIcon {
    color: #8D96A5;
    font-size: 14px;
    font-weight: 700;
}

QProgressBar {
    background: #2B2B2B;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    height: 8px;
}

QProgressBar::chunk {
    background: #2979FF;
    border-radius: 4px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 2px 0;
}

QScrollBar::handle:vertical {
    background: #3A3A3A;
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar::handle:vertical:hover {
    background: #505050;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QTextEdit#ActivityLog {
    background: #101010;
    color: #AEB7C4;
    border: 1px solid #2B2B2B;
    border-radius: 12px;
    padding: 10px;
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: 10px;
    selection-background-color: #2979FF;
    selection-color: #FFFFFF;
}

QPushButton {
    min-height: 34px;
    padding: 0 15px;
    border-radius: 9px;
    border: 1px solid #363636;
    background: #252525;
    color: #D7DCE3;
    font-size: 10px;
    font-weight: 700;
}

QPushButton:hover {
    background: #303030;
    border-color: #444444;
}

QPushButton:pressed {
    background: #1B1B1B;
}

QPushButton:disabled {
    background: #1A1A1A;
    border-color: #252525;
    color: #626A75;
}

QPushButton#Primary {
    background: #2979FF;
    border-color: #2979FF;
    color: #FFFFFF;
    min-width: 130px;
}

QPushButton#Primary:hover {
    background: #448AFF;
    border-color: #448AFF;
}

QPushButton#Primary:pressed {
    background: #1E63D8;
}

QPushButton#Primary:disabled {
    background: #183663;
    border-color: #183663;
    color: #607DAA;
}
"""


class SetupWindow(QDialog):
    """Automatic first-run dependency setup for PhoneView."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("PhoneView — Setup")
        self.resize(820, 620)
        self.setMinimumSize(560, 430)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(PHONEVIEW_QSS)

        self.checker = DependencyChecker()
        self.process = None
        self.installing = False
        self.current_packages = []
        self.package_progress = {}
        self.rows = {}

        self.build_ui()
        QTimer.singleShot(250, self.run_check)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(11)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        brand = QVBoxLayout()
        brand.setSpacing(1)

        eyebrow = QLabel("ANDROID DESKTOP CLIENT")
        eyebrow.setObjectName("Eyebrow")
        eyebrow.setWordWrap(True)
        brand.addWidget(eyebrow)

        title = QLabel("PhoneView")
        title.setWordWrap(True)
        title.setFont(QFont("DejaVu Sans", 22, QFont.Bold))
        brand.addWidget(title)

        subtitle = QLabel("Preparing your environment")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        brand.addWidget(subtitle)

        header.addLayout(brand, 1)

        header_hint = QLabel("FIRST RUN")
        header_hint.setObjectName("Muted")
        header_hint.setWordWrap(True)
        header_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_hint.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        header.addWidget(header_hint)

        root.addLayout(header)

        # Status card
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 15, 16, 15)
        status_layout.setSpacing(9)

        accent = QFrame()
        accent.setObjectName("StatusAccent")
        accent.setFixedHeight(5)
        accent.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(accent)

        status_header = QHBoxLayout()
        status_header.setSpacing(10)

        status_text = QVBoxLayout()
        status_text.setSpacing(2)

        self.status = QLabel("Checking your system...")
        self.status.setObjectName("StatusTitle")
        self.status.setWordWrap(True)
        self.status.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        status_text.addWidget(self.status)

        self.detail = QLabel(
            "Checking ADB, scrcpy and required system libraries."
        )
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        status_text.addWidget(self.detail)

        status_header.addLayout(status_text, 1)

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Percent")
        self.percent_label.setWordWrap(True)
        self.percent_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        status_header.addWidget(self.percent_label)

        status_layout.addLayout(status_header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        status_layout.addWidget(self.progress)

        self.progress_text = QLabel("Initializing...")
        self.progress_text.setObjectName("Muted")
        self.progress_text.setWordWrap(True)
        status_layout.addWidget(self.progress_text)

        root.addWidget(status_card)

        # Components
        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dependencies.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        dep_layout = QVBoxLayout(dependencies)
        dep_layout.setContentsMargins(14, 12, 14, 12)
        dep_layout.setSpacing(8)

        dep_header = QHBoxLayout()

        dep_title = QLabel("Required components")
        dep_title.setObjectName("SectionTitle")
        dep_title.setWordWrap(True)
        dep_header.addWidget(dep_title)
        dep_header.addStretch(1)

        dep_hint = QLabel("3 checks")
        dep_hint.setObjectName("Muted")
        dep_hint.setWordWrap(True)
        dep_header.addWidget(dep_hint)

        dep_layout.addLayout(dep_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        content = QWidget()
        content.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        component_layout = QVBoxLayout(content)
        component_layout.setContentsMargins(0, 0, 0, 0)
        component_layout.setSpacing(6)

        for key in ("adb", "scrcpy", "xcb"):
            component_layout.addWidget(
                self.create_dependency_row(key)
            )

        component_layout.addItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Minimum,
                QSizePolicy.Expanding,
            )
        )

        scroll.setWidget(content)
        dep_layout.addWidget(scroll)

        root.addWidget(dependencies)

        # Activity
        activity_header = QHBoxLayout()

        activity_title = QLabel("Live activity")
        activity_title.setObjectName("SectionTitle")
        activity_title.setWordWrap(True)
        activity_header.addWidget(activity_title)
        activity_header.addStretch(1)

        activity_hint = QLabel("SYSTEM OUTPUT")
        activity_hint.setObjectName("Muted")
        activity_hint.setWordWrap(True)
        activity_hint.setFont(QFont("DejaVu Sans Mono", 8))
        activity_header.addWidget(activity_hint)

        root.addLayout(activity_header)

        self.log = QTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.setPlaceholderText(
            "Waiting for setup activity..."
        )
        self.log.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self.log.setMinimumHeight(65)
        self.log.setFont(QFont("DejaVu Sans Mono", 9))
        root.addWidget(self.log, 1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.retry_button = QPushButton("Check again")
        self.retry_button.setFont(
            QFont("DejaVu Sans", 9, QFont.Bold)
        )
        self.retry_button.clicked.connect(self.run_check)

        footer.addWidget(self.retry_button)
        footer.addItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Expanding,
                QSizePolicy.Minimum,
            )
        )

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(
            QFont("DejaVu Sans", 9, QFont.Bold)
        )
        self.cancel_button.clicked.connect(self.cancel_setup)

        self.continue_button = QPushButton("Start PhoneView")
        self.continue_button.setObjectName("Primary")
        self.continue_button.setFont(
            QFont("DejaVu Sans", 9, QFont.Bold)
        )
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setEnabled(False)

        footer.addWidget(self.cancel_button)
        footer.addWidget(self.continue_button)

        root.addLayout(footer)

    def create_dependency_row(self, key):
        row = QFrame()
        row.setObjectName("DependencyRow")
        row.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(9)

        icon = QLabel("○")
        icon.setObjectName("StatusIcon")
        icon.setWordWrap(True)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedWidth(24)

        name = QLabel({
            "adb": "Android Debug Bridge (ADB)",
            "scrcpy": "scrcpy",
            "xcb": "Qt XCB cursor support",
        }[key])
        name.setObjectName("DependencyName")
        name.setWordWrap(True)
        name.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        state = QLabel("Waiting")
        state.setObjectName("DependencyState")
        state.setWordWrap(True)
        state.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        state.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Preferred,
        )
        state.setMinimumWidth(78)
        state.setMaximumWidth(130)

        layout.addWidget(icon)
        layout.addWidget(name, 1)
        layout.addWidget(state)

        self.rows[key] = {
            "row": row,
            "icon": icon,
            "state": state,
        }
        return row

    def set_row(self, key, state, icon, color):
        item = self.rows.get(key)
        if not item:
            return

        item["icon"].setText(icon)
        item["icon"].setStyleSheet(
            f"color: {color};"
        )
        item["state"].setText(state)
        item["state"].setStyleSheet(
            f"color: {color};"
        )

    def write_log(self, text):
        if not text:
            return

        self.log.append(text.rstrip())

        scrollbar = self.log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_progress(self, value, text):
        value = max(0, min(100, int(value)))
        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")
        self.progress_text.setText(text)

    def run_check(self):
        if self.process is not None:
            return

        self.installing = False
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        self.status.setText("Checking your system...")
        self.detail.setText(
            "Detecting ADB, scrcpy and the required system libraries."
        )
        self.set_progress(5, "Scanning installed components...")
        self.write_log("Starting dependency check.")

        items = self.checker.check()
        missing = [item for item in items if not item["ok"]]

        for item in items:
            if item["ok"]:
                self.set_row(
                    item["id"], "Ready", "✓", "#4CAF50"
                )
                self.write_log(
                    f"✓ {item['name']} is ready."
                )
            else:
                self.set_row(
                    item["id"],
                    "Missing — will install",
                    "↓",
                    "#FFB300",
                )
                self.write_log(
                    f"↓ {item['name']} is missing."
                )

        if not missing:
            self.finish_success()
            return

        if (
            sys.platform.startswith("linux")
            and self.checker.command_exists("pkexec")
        ):
            self.status.setText("Missing components found")
            self.detail.setText(
                "PhoneView will install them automatically. "
                "You may only need to approve the system permission dialog."
            )
            self.set_progress(
                15,
                f"Preparing automatic installation of "
                f"{len(missing)} component(s)...",
            )
            QTimer.singleShot(500, self.start_install)
            return

        self.status.setText(
            "Automatic installation is unavailable"
        )
        self.detail.setText(
            self.manual_install_message()
        )
        self.set_progress(
            15,
            "Waiting for manual setup."
        )
        self.cancel_button.setEnabled(True)

    def start_install(self):
        if self.process is not None:
            return

        packages = self.checker.missing_linux_packages()

        if not packages:
            self.run_check()
            return

        self.installing = True
        self.current_packages = packages
        self.package_progress = {
            package: 0 for package in packages
        }

        self.retry_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        for package in packages:
            key = self.package_to_key(package)
            if key:
                self.set_row(
                    key, "Queued", "↓", "#2979FF"
                )

        self.status.setText("Preparing downloads...")
        self.detail.setText(
            "Requesting administrator permission and updating "
            "package information."
        )
        self.set_progress(
            20, "Updating package lists..."
        )
        self.write_log(
            "Automatic setup started."
        )
        self.write_log(
            "A system permission dialog may appear now."
        )

        self.process = QProcess(self)
        self.process.setProcessChannelMode(
            QProcess.MergedChannels
        )
        self.process.readyReadStandardOutput.connect(
            self.read_output
        )
        self.process.finished.connect(
            self.install_finished
        )
        self.process.errorOccurred.connect(
            self.process_error
        )

        self.process.start(
            "pkexec",
            [
                "apt-get",
                "-o", "Dpkg::Progress-Fancy=0",
                "-o", "APT::Status-Fd=1",
                "update",
            ],
        )

    def read_output(self):
        if not self.process:
            return

        data = bytes(
            self.process.readAllStandardOutput()
        ).decode(errors="replace")

        if not data:
            return

        for raw_line in data.replace(
            "\r", "\n"
        ).splitlines():
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("dlstatus:"):
                self.parse_download_status(line)
                continue

            self.write_log(line)

            lower = line.lower()

            if "reading package lists" in lower:
                self.set_progress(
                    max(self.progress.value(), 42),
                    "Reading package lists..."
                )
            elif "building dependency tree" in lower:
                self.set_progress(
                    max(self.progress.value(), 48),
                    "Building dependency tree..."
                )
            elif "building state information" in lower:
                self.set_progress(
                    max(self.progress.value(), 52),
                    "Building package state..."
                )
            elif "download complete" in lower:
                self.set_progress(
                    max(self.progress.value(), 65),
                    "Downloads complete. Installing..."
                )
            elif "unpacking" in lower:
                self.set_progress(
                    max(self.progress.value(), 72),
                    "Unpacking packages..."
                )
            elif "setting up" in lower:
                self.set_progress(
                    max(self.progress.value(), 84),
                    "Configuring packages..."
                )

    def parse_download_status(self, line):
        match = re.search(
            r"percent:(\d+(?:\.\d+)?)",
            line
        )

        if not match:
            return

        percent = float(match.group(1))
        overall = 20 + (percent * 0.48)

        self.set_progress(
            max(self.progress.value(), int(overall)),
            f"Downloading packages... {percent:.0f}%"
        )

    def install_finished(self, exit_code, exit_status):
        self.read_output()

        if exit_code != 0:
            self.fail_setup(
                "Package list update failed.",
                "The system package manager could not update "
                "its package information.",
                exit_code,
            )
            return

        self.write_log(
            "✓ Package lists updated successfully."
        )

        packages = self.checker.missing_linux_packages()

        if not packages:
            self.process = None
            self.run_check()
            return

        self.current_packages = packages
        self.status.setText(
            "Downloading and installing"
        )
        self.detail.setText(
            "PhoneView is installing: "
            + ", ".join(packages)
        )
        self.set_progress(
            58,
            "Downloading required packages..."
        )
        self.write_log(
            "Installing: " + ", ".join(packages)
        )

        try:
            self.process.finished.disconnect(
                self.install_finished
            )
        except (TypeError, RuntimeError):
            pass

        self.process.finished.connect(
            self.package_install_finished
        )

        self.process.start(
            "pkexec",
            [
                "apt-get",
                "-o", "Dpkg::Progress-Fancy=0",
                "-o", "APT::Status-Fd=1",
                "install",
                "-y",
            ] + packages,
        )

    def package_install_finished(
        self,
        exit_code,
        exit_status
    ):
        self.read_output()

        if exit_code != 0:
            self.fail_setup(
                "Installation failed.",
                "One or more required components could not "
                "be installed. The Activity log contains "
                "the system error.",
                exit_code,
            )
            return

        self.process = None
        self.installing = False

        self.set_progress(
            95,
            "Installation finished. Verifying..."
        )
        self.status.setText(
            "Verifying installation"
        )
        self.detail.setText(
            "Checking every component again before PhoneView starts."
        )
        self.write_log(
            "✓ Installation completed. "
            "Running final verification..."
        )

        QTimer.singleShot(
            800,
            self.run_check
        )

    def finish_success(self):
        self.process = None
        self.installing = False

        self.status.setText("Everything is ready")
        self.detail.setText(
            "All required components are installed. "
            "PhoneView can start now."
        )
        self.set_progress(
            100,
            "Setup completed successfully."
        )

        self.write_log(
            "✓ All dependencies are ready."
        )
        self.write_log(
            "✓ PhoneView is ready to start."
        )

        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.continue_button.setEnabled(True)

        for item in self.checker.check():
            if item["ok"]:
                self.set_row(
                    item["id"],
                    "Ready",
                    "✓",
                    "#4CAF50"
                )

    def fail_setup(
        self,
        title,
        detail,
        exit_code
    ):
        self.process = None
        self.installing = False

        self.status.setText(title)
        self.detail.setText(detail)
        self.set_progress(
            max(15, self.progress.value()),
            f"Operation failed (exit code {exit_code})."
        )

        self.write_log(
            f"✗ Operation failed with exit code {exit_code}."
        )

        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        for package in self.current_packages:
            key = self.package_to_key(package)

            if key:
                self.set_row(
                    key,
                    "Failed",
                    "!",
                    "#F44336"
                )

    def process_error(self, error):
        self.write_log(
            f"✗ Installer error: {error}"
        )
        self.status.setText(
            "Installer could not start"
        )
        self.detail.setText(
            "PhoneView could not start the system package installer."
        )

        self.process = None
        self.installing = False
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def package_to_key(self, package):
        return {
            "adb": "adb",
            "scrcpy": "scrcpy",
            "libxcb-cursor0": "xcb",
        }.get(package)

    def manual_install_message(self):
        if sys.platform.startswith("linux"):
            return (
                "Automatic installation requires the system "
                "authorization service (pkexec). Install the "
                "missing components manually, then click Check again."
            )

        if sys.platform == "darwin":
            return (
                "Automatic macOS installation will be added later. "
                "Install ADB and scrcpy, then click Check again."
            )

        return (
            "Automatic Windows installation will be added later. "
            "Install ADB and scrcpy, then click Check again."
        )

    def cancel_setup(self):
        if self.process is not None:
            self.write_log(
                "Cancelling current installation..."
            )
            self.process.kill()
            self.process = None

        self.installing = False
        self.reject()

    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process = None

        event.accept()

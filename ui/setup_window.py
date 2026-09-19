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
    background-color: #121212;
    color: #E0E0E0;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
    font-size: 12px;
}

QLabel {
    color: #E0E0E0;
    background: transparent;
}

QLabel#Subtitle,
QLabel#Muted {
    color: #9E9E9E;
}

QFrame#Card {
    background-color: #1E1E1E;
    border: 1px solid #2A2A2A;
    border-radius: 12px;
}

QFrame#DependencyRow {
    background-color: #181818;
    border: 1px solid #292929;
    border-radius: 8px;
}

QProgressBar {
    background-color: #2A2A2A;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    height: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #2979FF;
    border-radius: 4px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: #181818;
    width: 8px;
    margin: 2px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #424242;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #555555;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QTextEdit#ActivityLog {
    background-color: #0D0D0D;
    color: #BDBDBD;
    border: 1px solid #292929;
    border-radius: 10px;
    padding: 8px;
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: 11px;
    selection-background-color: #2979FF;
    selection-color: #FFFFFF;
}

QPushButton {
    min-height: 36px;
    padding: 0 16px;
    border-radius: 8px;
    border: 1px solid #383838;
    background-color: #242424;
    color: #E0E0E0;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #303030;
}

QPushButton:pressed {
    background-color: #191919;
}

QPushButton:disabled {
    background-color: #1A1A1A;
    color: #666666;
    border-color: #252525;
}

QPushButton#Primary {
    background-color: #2979FF;
    border-color: #2979FF;
    color: #FFFFFF;
}

QPushButton#Primary:hover {
    background-color: #448AFF;
}

QPushButton#Primary:pressed {
    background-color: #1E63D8;
}

QPushButton#Primary:disabled {
    background-color: #183663;
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
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # Header
        header = QVBoxLayout()
        header.setSpacing(2)

        title = QLabel("PhoneView")
        title.setWordWrap(True)
        title.setFont(QFont("DejaVu Sans", 24, QFont.Bold))

        subtitle = QLabel("Automatic first-run setup")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        subtitle.setFont(QFont("DejaVu Sans", 10))

        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        # Main status card
        status_card = QFrame()
        status_card.setObjectName("Card")
        status_card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)

        status_header = QHBoxLayout()
        status_header.setSpacing(8)

        self.status = QLabel("Checking your system...")
        self.status.setWordWrap(True)
        self.status.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        self.status.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        self.percent_label = QLabel("0%")
        self.percent_label.setWordWrap(True)
        self.percent_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        self.percent_label.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        self.percent_label.setSizePolicy(
            QSizePolicy.Minimum,
            QSizePolicy.Preferred,
        )

        status_header.addWidget(self.status, 1)
        status_header.addWidget(self.percent_label)
        status_layout.addLayout(status_header)

        self.detail = QLabel(
            "PhoneView is checking everything it needs before starting."
        )
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        status_layout.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        status_layout.addWidget(self.progress)

        self.progress_text = QLabel("Starting...")
        self.progress_text.setObjectName("Muted")
        self.progress_text.setWordWrap(True)
        self.progress_text.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )
        status_layout.addWidget(self.progress_text)

        root.addWidget(status_card)

        # Required components card
        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dependencies.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        dep_layout = QVBoxLayout(dependencies)
        dep_layout.setContentsMargins(14, 10, 14, 10)
        dep_layout.setSpacing(7)

        dep_title = QLabel("Required Components")
        dep_title.setWordWrap(True)
        dep_title.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        dep_layout.addWidget(dep_title)

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
            component_layout.addWidget(self.create_dependency_row(key))

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

        # Live activity
        activity_title = QLabel("Live Activity")
        activity_title.setWordWrap(True)
        activity_title.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        root.addWidget(activity_title)

        self.log = QTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.setPlaceholderText(
            "Activity and installation output will appear here..."
        )
        self.log.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self.log.setMinimumHeight(70)
        self.log.setFont(QFont("DejaVu Sans Mono", 9))
        root.addWidget(self.log, 1)

        # Bottom buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        buttons.addItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Expanding,
                QSizePolicy.Minimum,
            )
        )

        self.retry_button = QPushButton("Check again")
        self.retry_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.retry_button.clicked.connect(self.run_check)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.cancel_button.clicked.connect(self.cancel_setup)

        self.continue_button = QPushButton("Start PhoneView")
        self.continue_button.setObjectName("Primary")
        self.continue_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setEnabled(False)

        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.continue_button)
        root.addLayout(buttons)

    def create_dependency_row(self, key):
        row = QFrame()
        row.setObjectName("DependencyRow")
        row.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon = QLabel("○")
        icon.setWordWrap(True)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFont(QFont("DejaVu Sans", 13, QFont.Bold))
        icon.setFixedWidth(22)

        name = QLabel({
            "adb": "Android Debug Bridge (ADB)",
            "scrcpy": "scrcpy",
            "xcb": "Qt XCB cursor support",
        }[key])
        name.setWordWrap(True)
        name.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
        name.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred,
        )

        state = QLabel("Waiting")
        state.setWordWrap(True)
        state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        state.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Preferred,
        )
        state.setMinimumWidth(72)
        state.setMaximumWidth(125)
        state.setStyleSheet("color: #9E9E9E;")

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
        item["icon"].setStyleSheet(f"color: {color};")
        item["state"].setText(state)
        item["state"].setStyleSheet(f"color: {color};")

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
                    item["id"],
                    "Ready",
                    "✓",
                    "#4CAF50",
                )
                self.write_log(f"✓ {item['name']} is ready.")
            else:
                self.set_row(
                    item["id"],
                    "Missing — will install",
                    "↓",
                    "#FFB300",
                )
                self.write_log(f"↓ {item['name']} is missing.")

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

        self.status.setText("Automatic installation is unavailable")
        self.detail.setText(self.manual_install_message())
        self.set_progress(15, "Waiting for manual setup.")
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
                    key,
                    "Queued",
                    "↓",
                    "#2979FF",
                )

        self.status.setText("Preparing downloads...")
        self.detail.setText(
            "Requesting administrator permission and updating "
            "package information."
        )
        self.set_progress(20, "Updating package lists...")
        self.write_log("Automatic setup started.")
        self.write_log(
            "A system permission dialog may appear now."
        )

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
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

        for raw_line in data.replace("\r", "\n").splitlines():
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
                    "Reading package lists...",
                )
            elif "building dependency tree" in lower:
                self.set_progress(
                    max(self.progress.value(), 48),
                    "Building dependency tree...",
                )
            elif "building state information" in lower:
                self.set_progress(
                    max(self.progress.value(), 52),
                    "Building package state...",
                )
            elif "download complete" in lower:
                self.set_progress(
                    max(self.progress.value(), 65),
                    "Downloads complete. Installing...",
                )
            elif "unpacking" in lower:
                self.set_progress(
                    max(self.progress.value(), 72),
                    "Unpacking packages...",
                )
            elif "setting up" in lower:
                self.set_progress(
                    max(self.progress.value(), 84),
                    "Configuring packages...",
                )

    def parse_download_status(self, line):
        match = re.search(
            r"percent:(\d+(?:\.\d+)?)",
            line,
        )

        if not match:
            return

        percent = float(match.group(1))
        overall = 20 + (percent * 0.48)

        self.set_progress(
            max(self.progress.value(), int(overall)),
            f"Downloading packages... {percent:.0f}%",
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
            "Downloading required packages...",
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
        exit_status,
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
            "Installation finished. Verifying...",
        )
        self.status.setText(
            "Verifying installation"
        )
        self.detail.setText(
            "Checking every component again before "
            "PhoneView starts."
        )
        self.write_log(
            "✓ Installation completed. "
            "Running final verification..."
        )

        QTimer.singleShot(800, self.run_check)

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
            "Setup completed successfully.",
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
                    "#4CAF50",
                )

    def fail_setup(
        self,
        title,
        detail,
        exit_code,
    ):
        self.process = None
        self.installing = False

        self.status.setText(title)
        self.detail.setText(detail)
        self.set_progress(
            max(15, self.progress.value()),
            f"Operation failed (exit code {exit_code}).",
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
                    "#F44336",
                )

    def process_error(self, error):
        self.write_log(
            f"✗ Installer error: {error}"
        )
        self.status.setText(
            "Installer could not start"
        )
        self.detail.setText(
            "PhoneView could not start the system "
            "package installer."
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
                "missing components manually, then click "
                "Check again."
            )

        if sys.platform == "darwin":
            return (
                "Automatic macOS installation will be added "
                "later. Install ADB and scrcpy, then click "
                "Check again."
            )

        return (
            "Automatic Windows installation will be added "
            "later. Install ADB and scrcpy, then click "
            "Check again."
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

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
    QSizePolicy,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.dependency_checker import DependencyChecker


class SetupWindow(QDialog):
    """Automatic first-run dependency setup for PhoneView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhoneView — Setup")
        self.resize(820, 620)
        self.setMinimumSize(560, 430)
        self.setSizeGripEnabled(True)

        self.checker = DependencyChecker()
        self.process = None
        self.installing = False
        self.current_packages = []
        self.package_progress = {}
        self.rows = {}

        self.build_ui()
        QTimer.singleShot(250, self.run_check)

    def build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: #0e1117;
                font-family: "DejaVu Sans", "Noto Sans", sans-serif;
                font-size: 12px;
                color: #edf2f7;
            }
            QLabel {
                color: #edf2f7;
            }
            QFrame#Card {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 14px;
            }
            QFrame#DependencyRow {
                background: #11161d;
                border: 1px solid #252c35;
                border-radius: 10px;
            }
            QLabel#Muted {
                color: #8b949e;
            }
            QLabel#State {
                font-weight: bold;
            }
            QProgressBar {
                height: 18px;
                border: 1px solid #30363d;
                border-radius: 9px;
                background: #0d1117;
                text-align: center;
                color: #edf2f7;
            }
            QProgressBar::chunk {
                background: #3b82f6;
                border-radius: 8px;
            }
            QTextEdit {
                background: #090c10;
                color: #aab4c3;
                border: 1px solid #30363d;
                border-radius: 10px;
                padding: 8px;
                font-family: monospace;
            }
            QPushButton {
                min-height: 40px;
                padding: 0 10px;
                border-radius: 9px;
                border: 1px solid #30363d;
                background: #21262d;
                color: #edf2f7;
            }
            QPushButton:hover {
                background: #30363d;
            }
            QPushButton:disabled {
                color: #6e7681;
                background: #161b22;
            }
            QPushButton#Primary {
                background: #238636;
                border-color: #2ea043;
            }
            QPushButton#Primary:hover {
                background: #2ea043;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(9)

        title = QLabel("PhoneView")
        title.setFont(QFont("DejaVu Sans", 23, QFont.Bold))
        root.addWidget(title)

        subtitle = QLabel("Automatic first-run setup")
        subtitle.setObjectName("Muted")
        subtitle.setStyleSheet("color: #8b949e; font-size: 11px;")
        root.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        self.status = QLabel("Checking your system...")
        self.status.setFont(QFont("DejaVu Sans", 13, QFont.Bold))
        header.addWidget(self.status)
        header.addStretch(1)

        self.percent_label = QLabel("0%")
        self.percent_label.setFont(QFont("DejaVu Sans", 12, QFont.Bold))
        header.addWidget(self.percent_label)
        card_layout.addLayout(header)

        self.detail = QLabel("PhoneView is checking everything it needs before starting.")
        self.detail.setObjectName("Muted")
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(28)
        self.detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        card_layout.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("")
        card_layout.addWidget(self.progress)

        self.progress_text = QLabel("Starting...")
        self.progress_text.setObjectName("Muted")
        self.progress_text.setStyleSheet("color: #8b949e; font-size: 10px;")
        self.progress_text.setWordWrap(True)
        self.progress_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        card_layout.addWidget(self.progress_text)

        root.addWidget(card)

        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dep_layout = QVBoxLayout(dependencies)
        dep_layout.setContentsMargins(14, 12, 14, 12)
        dep_layout.setSpacing(5)

        dep_title = QLabel("Required components")
        dep_title.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        dep_layout.addWidget(dep_title)

        for key in ("adb", "scrcpy", "xcb"):
            row = self.create_dependency_row(key)
            dep_layout.addWidget(row)

        root.addWidget(dependencies)

        activity_title = QLabel("Live activity")
        activity_title.setFont(QFont("DejaVu Sans", 11, QFont.Bold))
        root.addWidget(activity_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setMinimumHeight(80)
        self.log.setFont(QFont("DejaVu Sans Mono", 9))
        root.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        self.retry_button = QPushButton("Check again")
        self.retry_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.retry_button.clicked.connect(self.run_check)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.cancel_button.clicked.connect(self.cancel_setup)

        self.continue_button = QPushButton("Start PhoneView")
        self.continue_button.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        self.continue_button.setObjectName("Primary")
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setEnabled(False)

        buttons.setSpacing(6)
        buttons.addWidget(self.retry_button, 1)
        buttons.addWidget(self.cancel_button, 1)
        buttons.addWidget(self.continue_button, 1)
        root.addLayout(buttons)

    def create_dependency_row(self, key):
        row = QFrame()
        row.setObjectName("DependencyRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 5, 10, 5)

        icon = QLabel("○")
        icon.setFixedWidth(20)
        icon.setFont(QFont("DejaVu Sans", 13, QFont.Bold))

        name = QLabel({
            "adb": "Android Debug Bridge (ADB)",
            "scrcpy": "scrcpy",
            "xcb": "Qt XCB cursor support",
        }[key])
        name.setFont(QFont("DejaVu Sans", 10, QFont.Bold))
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name.setWordWrap(True)

        state = QLabel("Waiting")
        state.setObjectName("State")
        state.setMinimumWidth(95)
        state.setMaximumWidth(125)
        state.setWordWrap(True)
        state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        state.setStyleSheet("color: #8b949e;")

        layout.addWidget(icon)
        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(state)

        self.rows[key] = {"row": row, "icon": icon, "state": state}
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
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

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
        self.detail.setText("Detecting ADB, scrcpy and the required system libraries.")
        self.set_progress(5, "Scanning installed components...")
        self.write_log("Starting dependency check.")

        items = self.checker.check()
        missing = [item for item in items if not item["ok"]]

        for item in items:
            if item["ok"]:
                self.set_row(item["id"], "Ready", "✓", "#3fb950")
                self.write_log(f"✓ {item['name']} is ready.")
            else:
                self.set_row(item["id"], "Missing — will install", "↓", "#d29922")
                self.write_log(f"↓ {item['name']} is missing.")

        if not missing:
            self.finish_success()
            return

        if sys.platform.startswith("linux") and self.checker.command_exists("pkexec"):
            self.status.setText("Missing components found")
            self.detail.setText("PhoneView will install them automatically. You may only need to approve the system permission dialog.")
            self.set_progress(15, f"Preparing automatic installation of {len(missing)} component(s)...")
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
        self.package_progress = {package: 0 for package in packages}

        self.retry_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        for package in packages:
            key = self.package_to_key(package)
            if key:
                self.set_row(key, "Queued", "↓", "#58a6ff")

        self.status.setText("Preparing downloads...")
        self.detail.setText("Requesting administrator permission and updating package information.")
        self.set_progress(20, "Updating package lists...")
        self.write_log("Automatic setup started.")
        self.write_log("A system permission dialog may appear now.")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.install_finished)
        self.process.errorOccurred.connect(self.process_error)

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

        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
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
                self.set_progress(max(self.progress.value(), 42), "Reading package lists...")
            elif "building dependency tree" in lower:
                self.set_progress(max(self.progress.value(), 48), "Building dependency tree...")
            elif "building state information" in lower:
                self.set_progress(max(self.progress.value(), 52), "Building package state...")
            elif "download complete" in lower:
                self.set_progress(max(self.progress.value(), 65), "Downloads complete. Installing...")
            elif "unpacking" in lower:
                self.set_progress(max(self.progress.value(), 72), "Unpacking packages...")
            elif "setting up" in lower:
                self.set_progress(max(self.progress.value(), 84), "Configuring packages...")

    def parse_download_status(self, line):
        # APT status format can vary by version. We only use values we can parse safely.
        match = re.search(r'percent:(\d+(?:\.\d+)?)', line)
        if not match:
            return

        percent = float(match.group(1))
        overall = 20 + (percent * 0.48)
        self.set_progress(max(self.progress.value(), int(overall)), f"Downloading packages... {percent:.0f}%")

    def install_finished(self, exit_code, exit_status):
        self.read_output()

        if exit_code != 0:
            self.fail_setup(
                "Package list update failed.",
                "The system package manager could not update its package information.",
                exit_code,
            )
            return

        self.write_log("✓ Package lists updated successfully.")

        packages = self.checker.missing_linux_packages()
        if not packages:
            self.process = None
            self.run_check()
            return

        self.current_packages = packages
        self.status.setText("Downloading and installing")
        self.detail.setText("PhoneView is installing: " + ", ".join(packages))
        self.set_progress(58, "Downloading required packages...")
        self.write_log("Installing: " + ", ".join(packages))

        try:
            self.process.finished.disconnect(self.install_finished)
        except (TypeError, RuntimeError):
            pass

        self.process.finished.connect(self.package_install_finished)
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

    def package_install_finished(self, exit_code, exit_status):
        self.read_output()

        if exit_code != 0:
            self.fail_setup(
                "Installation failed.",
                "One or more required components could not be installed. The Activity log contains the system error.",
                exit_code,
            )
            return

        self.process = None
        self.installing = False
        self.set_progress(95, "Installation finished. Verifying...")
        self.status.setText("Verifying installation")
        self.detail.setText("Checking every component again before PhoneView starts.")
        self.write_log("✓ Installation completed. Running final verification...")
        QTimer.singleShot(800, self.run_check)

    def finish_success(self):
        self.process = None
        self.installing = False
        self.status.setText("Everything is ready")
        self.detail.setText("All required components are installed. PhoneView can start now.")
        self.set_progress(100, "Setup completed successfully.")
        self.write_log("✓ All dependencies are ready.")
        self.write_log("✓ PhoneView is ready to start.")
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.continue_button.setEnabled(True)

        for item in self.checker.check():
            if item["ok"]:
                self.set_row(item["id"], "Ready", "✓", "#3fb950")

    def fail_setup(self, title, detail, exit_code):
        self.process = None
        self.installing = False
        self.status.setText(title)
        self.detail.setText(detail)
        self.set_progress(max(15, self.progress.value()), f"Operation failed (exit code {exit_code}).")
        self.write_log(f"✗ Operation failed with exit code {exit_code}.")
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        for package in self.current_packages:
            key = self.package_to_key(package)
            if key:
                self.set_row(key, "Failed", "!", "#f85149")

    def process_error(self, error):
        self.write_log(f"✗ Installer error: {error}")
        self.status.setText("Installer could not start")
        self.detail.setText("PhoneView could not start the system package installer.")
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
            packages = self.checker.missing_linux_packages()
            return (
                "Automatic installation requires the system authorization service (pkexec). "
                "Install the missing components manually, then click Check again."
            )
        if sys.platform == "darwin":
            return "Automatic macOS installation will be added later. Install ADB and scrcpy, then click Check again."
        return "Automatic Windows installation will be added later. Install ADB and scrcpy, then click Check again."

    def cancel_setup(self):
        if self.process is not None:
            self.write_log("Cancelling current installation...")
            self.process.kill()
            self.process = None
        self.installing = False
        self.reject()

    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process = None
        event.accept()

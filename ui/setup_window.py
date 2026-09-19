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
QDialog { background: #0B0D10; color: #E8EDF5; font-family: "DejaVu Sans", "Noto Sans", sans-serif; }
QLabel { color: #E8EDF5; background: transparent; }
QLabel#Eyebrow { color: #6E9BFF; font-size: 9px; font-weight: 800; }
QLabel#Subtitle, QLabel#Muted { color: #7F8998; font-size: 10px; }
QLabel#SectionTitle { color: #DCE3ED; font-size: 10px; font-weight: 800; }
QLabel#StatusTitle { color: #F4F7FB; font-size: 17px; font-weight: 800; }
QLabel#StatusDetail { color: #8994A5; font-size: 10px; }
QLabel#Percent { color: #6E9BFF; font-size: 18px; font-weight: 800; }
QLabel#SectionMeta { color: #667181; font-size: 9px; }
QFrame#TopLine { background: #397BFF; border-radius: 2px; }
QFrame#StatusCard { background: #13171D; border: 1px solid #222A34; border-radius: 18px; }
QFrame#StatusGlow { background: #13264A; border: none; border-radius: 9px; }
QFrame#Card { background: #11151A; border: 1px solid #202832; border-radius: 16px; }
QFrame#DependencyRow { background: #151A20; border: 1px solid #222A34; border-radius: 11px; }
QFrame#DependencyRow:hover { background: #181F27; border-color: #2C3745; }
QLabel#DependencyName { color: #DCE3ED; font-size: 10px; font-weight: 700; }
QLabel#DependencyState { color: #7F8998; font-size: 9px; font-weight: 800; }
QLabel#StatusIcon { color: #7F8998; font-size: 10px; font-weight: 800; }
QProgressBar { background: #202731; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #397BFF; border-radius: 4px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #303A47; min-height: 22px; border-radius: 2px; }
QScrollBar::handle:vertical:hover { background: #465365; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTextEdit#ActivityLog { background: #090C0F; color: #98A5B6; border: 1px solid #202832; border-radius: 13px; padding: 10px; font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace; font-size: 9px; selection-background-color: #245FCA; selection-color: #FFFFFF; }
QPushButton { min-height: 34px; padding: 0 14px; border-radius: 9px; border: 1px solid #2A333F; background: #171C22; color: #C8D0DB; font-size: 9px; font-weight: 800; }
QPushButton:hover { background: #202731; border-color: #384454; color: #F0F4F8; }
QPushButton:pressed { background: #11151A; }
QPushButton:disabled { background: #14181D; border-color: #1D242D; color: #4F5967; }
QPushButton#Primary { background: #2D6BEF; border-color: #2D6BEF; color: #FFFFFF; min-width: 138px; }
QPushButton#Primary:hover { background: #4380FF; border-color: #4380FF; }
QPushButton#Primary:pressed { background: #2459C7; }
QPushButton#Primary:disabled { background: #172C50; border-color: #172C50; color: #526B91; }
QPushButton#Quiet { background: transparent; border-color: transparent; color: #7E8999; }
QPushButton#Quiet:hover { background: #171C22; border-color: #252E39; color: #D4DCE7; }
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
        root.setContentsMargins(22, 19, 22, 17)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(12)
        brand = QVBoxLayout()
        brand.setSpacing(2)

        eyebrow = QLabel("PHONEVIEW  /  ANDROID DESKTOP CLIENT")
        eyebrow.setObjectName("Eyebrow")
        brand.addWidget(eyebrow)

        title = QLabel("PhoneView")
        title.setFont(QFont("DejaVu Sans", 23, QFont.Bold))
        brand.addWidget(title)

        subtitle = QLabel("Secure first-run environment setup")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        brand.addWidget(subtitle)

        header.addLayout(brand, 1)

        badge = QLabel("FIRST RUN")
        badge.setObjectName("Muted")
        badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(badge)
        root.addLayout(header)

        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(10)

        line = QFrame()
        line.setObjectName("TopLine")
        line.setFixedHeight(4)
        status_layout.addWidget(line)

        status_row = QHBoxLayout()
        status_row.setSpacing(14)

        glow = QFrame()
        glow.setObjectName("StatusGlow")
        glow.setFixedSize(42, 42)
        glow_layout = QVBoxLayout(glow)
        glow_layout.setContentsMargins(0, 0, 0, 0)
        self.status_icon = QLabel("●")
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setStyleSheet("color:#5B8FFF; font-size:15px;")
        glow_layout.addWidget(self.status_icon)
        status_row.addWidget(glow)

        status_text = QVBoxLayout()
        status_text.setSpacing(3)
        self.status = QLabel("Checking your system...")
        self.status.setObjectName("StatusTitle")
        self.status.setWordWrap(True)
        status_text.addWidget(self.status)

        self.detail = QLabel("Detecting ADB, scrcpy and required system libraries.")
        self.detail.setObjectName("StatusDetail")
        self.detail.setWordWrap(True)
        status_text.addWidget(self.detail)
        status_row.addLayout(status_text, 1)

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Percent")
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_row.addWidget(self.percent_label)
        status_layout.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        status_layout.addWidget(self.progress)

        self.progress_text = QLabel("Initializing setup...")
        self.progress_text.setObjectName("Muted")
        self.progress_text.setWordWrap(True)
        status_layout.addWidget(self.progress_text)
        root.addWidget(status_card)

        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dep_layout = QVBoxLayout(dependencies)
        dep_layout.setContentsMargins(14, 12, 14, 12)
        dep_layout.setSpacing(8)

        dep_header = QHBoxLayout()
        dep_title = QLabel("Required components")
        dep_title.setObjectName("SectionTitle")
        dep_header.addWidget(dep_title)
        dep_header.addStretch(1)
        dep_hint = QLabel("3 COMPONENTS")
        dep_hint.setObjectName("SectionMeta")
        dep_header.addWidget(dep_hint)
        dep_layout.addLayout(dep_header)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        component_layout = QVBoxLayout(content)
        component_layout.setContentsMargins(0, 0, 0, 0)
        component_layout.setSpacing(6)
        for key in ("adb", "scrcpy", "xcb"):
            component_layout.addWidget(self.create_dependency_row(key))
        component_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(142)
        scroll.setWidget(content)
        dep_layout.addWidget(scroll)
        root.addWidget(dependencies)

        activity_header = QHBoxLayout()
        activity_title = QLabel("Activity")
        activity_title.setObjectName("SectionTitle")
        activity_header.addWidget(activity_title)
        activity_header.addStretch(1)
        activity_hint = QLabel("LIVE SYSTEM OUTPUT")
        activity_hint.setObjectName("SectionMeta")
        activity_header.addWidget(activity_hint)
        root.addLayout(activity_header)

        self.log = QTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.setPlaceholderText("Waiting for setup activity...")
        self.log.setMinimumHeight(68)
        self.log.setFont(QFont("DejaVu Sans Mono", 9))
        root.addWidget(self.log, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.retry_button = QPushButton("↻  Check again")
        self.retry_button.setObjectName("Quiet")
        self.retry_button.clicked.connect(self.run_check)
        footer.addWidget(self.retry_button)
        footer.addStretch(1)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_setup)
        self.continue_button = QPushButton("Start PhoneView")
        self.continue_button.setObjectName("Primary")
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

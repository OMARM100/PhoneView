import os
import re
import shutil
import subprocess
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
        self.auth_agent_process = None
        self.auth_agent_started_by_us = False
        self.installing = False
        self.cancelling = False
        self.current_packages = []
        self.package_progress = {}
        self.rows = {}
        self.install_timer = None
        self.pending_scrcpy_build = False

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
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

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
        name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        state = QLabel("Waiting")
        state.setObjectName("DependencyState")
        state.setWordWrap(True)
        state.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        state.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        state.setMinimumWidth(78)
        state.setMaximumWidth(130)

        layout.addWidget(icon)
        layout.addWidget(name, 1)
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
        if text:
            self.log.append(text.rstrip())
            scrollbar = self.log.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def set_progress(self, value, text):
        value = max(0, min(100, int(value)))
        self.progress.setValue(value)
        self.percent_label.setText(f"{value}%")
        self.progress_text.setText(text)

    def run_check(self):
        if self.process is not None or self.install_timer is not None:
            return

        self.installing = False
        self.cancelling = False
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
                self.set_row(item["id"], "Ready", "✓", "#4CAF50")
                self.write_log(f"✓ {item['name']} is ready.")
            else:
                self.set_row(item["id"], "Missing — will install", "↓", "#FFB300")
                self.write_log(f"↓ {item['name']} is missing.")

        if not missing:
            self.finish_success()
            return

        if sys.platform.startswith("linux") and (
            any(item["id"] == "scrcpy" for item in missing) or self.pkexec_path()
        ):
            self.status.setText("Preparing automatic installation")
            self.detail.setText(
                "PhoneView installs the required system packages, then builds its pinned "
                "scrcpy 4.1 engine with the integrated mapping editor."
            )
            self.set_progress(15, f"Preparing automatic installation of {len(missing)} component(s)...")
            self.install_timer = QTimer(self)
            self.install_timer.setSingleShot(True)
            self.install_timer.timeout.connect(self.start_install)
            self.install_timer.start(500)
            return

        self.status.setText("Automatic installation is unavailable")
        self.detail.setText(self.manual_install_message())
        self.set_progress(15, "Waiting for manual setup.")
        self.cancel_button.setEnabled(True)

    def start_install(self):
        self.install_timer = None
        if self.process is not None or self.cancelling:
            return

        packages = self.checker.missing_linux_packages()
        if not packages:
            self.run_check()
            return

        # The checker intentionally does not expose the pseudo-package\n        # "phoneview-scrcpy" in the APT package list. Build state must therefore\n        # be derived from the actual PhoneView engine check, otherwise setup can\n        # finish installing system packages and immediately loop forever.\n        self.pending_scrcpy_build = not self.checker.scrcpy_ok()\n        system_packages = [
            package for package in packages
            if package != "phoneview-scrcpy"
        ]

        self.installing = True
        self.cancelling = False
        self.current_packages = system_packages
        self.package_progress = {package: 0 for package in system_packages}

        self.retry_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        if self.pending_scrcpy_build:
            self.set_row("scrcpy", "Build required", "↓", "#2979FF")
            self.write_log("PhoneView requires its pinned scrcpy 4.1 engine.")
            self.write_log("New upstream scrcpy releases will not be checked or installed.")

        for package in system_packages:
            key = self.package_to_key(package)
            if key:
                self.set_row(key, "Queued", "↓", "#2979FF")

        if not system_packages:
            self.start_scrcpy_build()
            return

        self.status.setText("Administrator permission required")
        self.detail.setText(
            "PhoneView will install the required Linux packages first. "
            "After that, it will build the pinned scrcpy 4.1 PhoneView engine."
        )
        self.set_progress(20, "Waiting for the system authorization dialog...")
        self.write_log("Automatic system setup started.")
        self.write_log("System packages: " + ", ".join(system_packages))
        self.write_log(f"Using administrator authorization: {self.pkexec_path()}")
        self.write_log("Password security: authentication is handled by the operating system.")
        self.write_log("Requesting graphical system authorization (no Terminal window).")

        self.install_timer = QTimer(self)
        self.install_timer.setSingleShot(True)
        self.install_timer.timeout.connect(self.start_authorized_update)
        self.install_timer.start(700)

    def start_scrcpy_build(self):
        if self.process is not None or self.cancelling:
            return

        self.installing = True
        self.retry_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        self.set_row("scrcpy", "Building PhoneView engine", "↓", "#2979FF")
        self.status.setText("Building PhoneView scrcpy")
        self.detail.setText(
            "Building pinned scrcpy 4.1 with the native PhoneView mapping editor."
        )
        self.set_progress(18, "Preparing the pinned scrcpy 4.1 build...")
        self.write_log("PhoneView scrcpy build started.")
        self.write_log("Pinned source: Genymobile/scrcpy v4.1.")
        self.write_log("Automatic upstream scrcpy updates are disabled.")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_scrcpy_output)
        self.process.finished.connect(self.scrcpy_build_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.process.start(
            sys.executable,
            ["-m", "core.scrcpy_installer"],
        )

    def read_scrcpy_output(self):
        if not self.process:
            return

        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if not data:
            return

        for raw_line in data.replace("\r", "\n").splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("PROGRESS:"):
                try:
                    percent = int(float(line.split(":", 1)[1]))
                    self.set_progress(max(18, min(96, percent)), f"Building PhoneView scrcpy... {percent}%")
                except ValueError:
                    pass
                continue

            if line.startswith("ERROR:"):
                self.write_log("✗ " + line[6:])
                continue

            self.write_log(line)

    def scrcpy_build_finished(self, exit_code, exit_status):
        self.read_scrcpy_output()
        if self.cancelling:
            return

        self.cleanup_process()

        if exit_code != 0:
            self.fail_setup(
                "scrcpy build failed",
                "PhoneView could not build its pinned scrcpy 4.1 engine. "
                "Check the Activity log for the exact error.",
                exit_code,
            )
            return

        items = self.checker.check()
        scrcpy_item = next(item for item in items if item["id"] == "scrcpy")
        if not scrcpy_item["ok"]:
            self.fail_setup(
                "scrcpy verification failed",
                "The pinned PhoneView scrcpy build finished, but the engine could not be verified.",
                1,
            )
            return

        self.write_log("✓ Pinned PhoneView scrcpy 4.1 build passed final verification.")
        self.set_row("scrcpy", "Ready", "✓", "#4CAF50")
        self.set_progress(92, "PhoneView scrcpy is ready. Checking remaining system components...")

        remaining = [
            item for item in items
            if not item["ok"] and item["id"] != "scrcpy"
        ]

        if not remaining:
            self.finish_success()
            return

        if not self.pkexec_path():
            self.fail_setup(
                "System components still need authorization",
                "The pinned scrcpy engine is ready, but remaining system packages require pkexec.",
                1,
            )
            return

        # Continue with any remaining system packages such as XCB.
        self.current_packages = [item["package"] for item in remaining if item.get("package")]
        self.start_install()

    def start_authorized_update(self):
        self.install_timer = None
        if self.cancelling or not self.installing or self.process is not None:
            return

        pkexec = self.pkexec_path()
        if not pkexec:
            self.fail_setup(
                "Administrator authorization is unavailable.",
                "pkexec is no longer available on this system.",
                1,
            )
            return

        self.status.setText("Administrator permission required")
        self.detail.setText(
            "The system authentication dialog should appear now. "
            "Enter your password only in that system dialog."
        )
        self.set_progress(20, "Preparing the graphical system authorization agent...")
        self.log_desktop_session()

        if not self.ensure_graphical_auth_agent():
            self.fail_setup(
                "No graphical Polkit authentication agent found.",
                "This Xfce session does not currently have a graphical Polkit authentication agent. "
                "PhoneView will not collect your password or fall back to a Terminal prompt. "
                "Install a graphical Polkit agent once, then click Check again.",
                127,
            )
            return

        self.write_log("Delegating authentication directly to the system Polkit agent.")
        self.write_log(
            "No password is requested, read, stored, or handled by PhoneView."
        )
        self.write_log("Waiting for the Polkit agent to register with the desktop session...")
        QTimer.singleShot(1200, self.launch_authorized_update)

    def launch_authorized_update(self):
        if self.cancelling or not self.installing or self.process is not None:
            return

        pkexec = self.pkexec_path()
        if not pkexec:
            self.fail_setup(
                "Administrator authorization is unavailable.",
                "pkexec is no longer available on this system.",
                1,
            )
            return

        self.write_log("Starting privileged package manager without a Terminal password prompt.")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.install_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.process.started.connect(lambda: self.write_log("✓ System package installer process started."))

        self.process.start(
            pkexec,
            [
                "apt-get",
                "-o", "Dpkg::Progress-Fancy=0",
                "-o", "APT::Status-Fd=1",
                "update",
            ],
        )

    def log_desktop_session(self):
        """Log session information without exposing credentials or secrets."""
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "unknown")
        session = os.environ.get("XDG_SESSION_DESKTOP", "unknown")
        display = bool(os.environ.get("DISPLAY"))
        wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        self.write_log(f"Desktop session: {desktop} / {session}")
        self.write_log(
            "Graphical display session: "
            + ("available" if (display or wayland) else "not detected")
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
        match = re.search(r"percent:(\d+(?:\.\d+)?)", line)
        if not match:
            return
        percent = float(match.group(1))
        overall = 20 + (percent * 0.48)
        self.set_progress(max(self.progress.value(), int(overall)), f"Downloading packages... {percent:.0f}%")

    def install_finished(self, exit_code, exit_status):
        self.read_output()
        if self.cancelling:
            return

        if exit_code != 0:
            self.fail_setup(
                "Package list update failed.",
                "The system package manager could not update its package information. "
                "If authentication was cancelled, simply click Check again.",
                exit_code,
            )
            return

        self.write_log("✓ Package lists updated successfully.")
        packages = [
            package
            for package in self.checker.missing_linux_packages()
            if package != "phoneview-scrcpy"
        ]
        if not packages:
            self.cleanup_process()
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

        pkexec = self.pkexec_path()
        if not pkexec:
            self.fail_setup(
                "Administrator authorization is unavailable.",
                "pkexec disappeared before installation could start.",
                1,
            )
            return

        self.write_log(f"Starting package installation with: {pkexec}")
        self.process.start(
            pkexec,
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
        if self.cancelling:
            return

        if exit_code != 0:
            self.fail_setup(
                "Installation failed.",
                "One or more required components could not be installed. "
                "The Activity log contains the system error.",
                exit_code,
            )
            return

        self.installing = False
        self.cleanup_process()

        if self.pending_scrcpy_build:
            self.pending_scrcpy_build = False
            self.write_log("✓ System packages installed.")
            self.set_progress(16, "System prerequisites are ready. Building PhoneView scrcpy...")
            QTimer.singleShot(500, self.start_scrcpy_build)
            return

        self.set_progress(95, "Installation finished. Verifying...")
        self.status.setText("Verifying installation")
        self.detail.setText("Checking every component again before PhoneView starts.")
        self.write_log("✓ Installation completed. Running final verification...")
        QTimer.singleShot(800, self.run_check)

    def finish_success(self):
        self.cleanup_process()
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
                self.set_row(item["id"], "Ready", "✓", "#4CAF50")

    def fail_setup(self, title, detail, exit_code):
        self.installing = False
        self.status.setText(title)
        self.detail.setText(detail)
        self.set_progress(max(15, self.progress.value()), f"Operation failed (exit code {exit_code}).")
        self.write_log(f"✗ Operation failed with exit code {exit_code}.")
        self.cleanup_process()
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        for package in self.current_packages:
            key = self.package_to_key(package)
            if key:
                self.set_row(key, "Failed", "!", "#F44336")

    def process_error(self, error):
        if self.cancelling:
            return
        self.write_log(f"✗ Installer error: {error}")
        self.status.setText("Installer could not start")
        self.detail.setText(
            "PhoneView could not start the system package installer. "
            "Authentication is delegated to Polkit; PhoneView never collects "
            "your password."
        )
        self.installing = False
        self.cleanup_process()
        self.retry_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

    def cleanup_process(self):
        process = self.process
        self.process = None
        if process is None:
            return
        for signal, slot in (
            (process.readyReadStandardOutput, self.read_output),
            (process.errorOccurred, self.process_error),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        process.deleteLater()

    def package_to_key(self, package):
        return {
            "adb": "adb",
            "scrcpy": "scrcpy",
            "phoneview-scrcpy": "scrcpy",
            "libxcb-cursor0": "xcb",
        }.get(package)

    def pkexec_path(self):
        if not sys.platform.startswith("linux"):
            return None
        if self.checker.command_exists("pkexec"):
            return "pkexec"
        for path in ("/usr/bin/pkexec", "/bin/pkexec"):
            if os.path.isfile(path):
                return path
        return None

    def manual_install_message(self):
        if sys.platform.startswith("linux"):
            return (
                "Automatic installation requires pkexec (the system authorization helper). "
                "It is not available on this system. Install it once with: "
                "sudo apt install policykit-1. Then click Check again."
            )
        if sys.platform == "darwin":
            return "Automatic macOS installation will be added later. Install ADB and scrcpy, then click Check again."
        return "Automatic Windows installation will be added later. Install ADB and scrcpy, then click Check again."

    def find_graphical_auth_agent(self):
        """Return a known graphical Polkit agent executable, if installed."""
        candidates = [
            "/usr/libexec/xfce-polkit",
            "/usr/bin/xfce-polkit",
            "/usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1",
            "/usr/libexec/polkit-gnome-authentication-agent-1",
            "/usr/libexec/polkit-mate-authentication-agent-1",
            "/usr/bin/lxpolkit",
            "/usr/bin/mate-polkit",
        ]

        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        for command in (
            "xfce-polkit",
            "polkit-gnome-authentication-agent-1",
            "polkit-mate-authentication-agent-1",
            "lxpolkit",
            "mate-polkit",
        ):
            found = shutil.which(command)
            if found:
                return found

        return None

    def graphical_auth_agent_running(self):
        """Check whether a known graphical Polkit agent is already running."""
        process_names = (
            "polkit-gnome-authentication-agent-1",
            "polkit-mate-authentication-agent-1",
            "xfce-polkit",
            "lxpolkit",
            "mate-polkit",
        )

        try:
            result = subprocess.run(
                ["ps", "-u", str(os.getuid()), "-o", "args="],
                capture_output=True,
                text=True,
                timeout=3,
            )
            output = result.stdout.lower()
            return any(name.lower() in output for name in process_names)
        except (OSError, subprocess.SubprocessError):
            return False

    def ensure_graphical_auth_agent(self):
        """
        Make sure the current desktop session has a graphical Polkit agent.

        PhoneView never implements authentication itself. If a supported agent is
        installed but its desktop autostart entry did not run, PhoneView may
        launch that agent so Polkit can display its normal system dialog.
        """
        if self.graphical_auth_agent_running():
            self.write_log("✓ Graphical Polkit authentication agent is already running.")
            return True

        agent = self.find_graphical_auth_agent()
        if not agent:
            self.write_log("✗ No installed graphical Polkit authentication agent was found.")
            return False

        self.write_log(f"Starting installed graphical Polkit agent: {agent}")

        try:
            process = QProcess(self)
            process.setProcessChannelMode(QProcess.MergedChannels)
            process.start(agent, [])

            if not process.waitForStarted(2500):
                self.write_log("✗ Graphical Polkit agent could not be started.")
                process.deleteLater()
                return False

            self.auth_agent_process = process
            self.auth_agent_started_by_us = True

            # Give the agent a moment to register itself with the current
            # session bus before pkexec sends its authorization request.
            QTimer.singleShot(1200, lambda: None)

            self.write_log("✓ Graphical Polkit agent started.")
            self.write_log("Waiting briefly for the XFCE Polkit agent to register with the session bus.")
            return True
        except (OSError, RuntimeError) as exc:
            self.write_log(f"✗ Could not start graphical Polkit agent: {exc}")
            return False

    def stop_auth_agent(self):
        process = self.auth_agent_process
        self.auth_agent_process = None
        if process is None:
            return
        if self.auth_agent_started_by_us:
            try:
                if process.state() != QProcess.NotRunning:
                    process.terminate()
                    if not process.waitForFinished(1500):
                        process.kill()
                        process.waitForFinished(500)
            except RuntimeError:
                pass
            process.deleteLater()
        self.auth_agent_started_by_us = False

    def cancel_setup(self):
        if self.install_timer is not None:
            timer = self.install_timer
            self.install_timer = None
            timer.stop()
            timer.deleteLater()

        if self.process is not None:
            self.cancelling = True
            self.write_log("Cancelling current installation...")
            process = self.process
            self.process = None
            try:
                if process.state() != QProcess.NotRunning:
                    process.terminate()
                    if not process.waitForFinished(2500):
                        process.kill()
                        process.waitForFinished(1000)
            except RuntimeError:
                pass
            process.deleteLater()

        self.installing = False
        self.stop_auth_agent()
        self.reject()

    def closeEvent(self, event):
        if self.install_timer is not None:
            self.write_log("Installation is preparing. Cancel the setup first.")
            event.ignore()
            return

        if self.process is not None and self.process.state() != QProcess.NotRunning:
            self.write_log("Installation is still running. Cancel the installation first.")
            event.ignore()
            return

        self.cleanup_process()
        self.stop_auth_agent()
        event.accept()

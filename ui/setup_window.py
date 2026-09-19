import sys
from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QTextEdit, QVBoxLayout, QFrame
)
from core.dependency_checker import DependencyChecker


class SetupWindow(QDialog):
    """Modern first-run dependency checker and installer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhoneView — First Run Setup")
        self.resize(820, 620)
        self.setMinimumSize(720, 560)

        self.checker = DependencyChecker()
        self.process = None
        self.install_phase = False

        self.build_ui()
        QTimer.singleShot(250, self.run_check)

    def build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background: #11151c;
                color: #e8edf5;
            }
            QLabel {
                color: #e8edf5;
            }
            QProgressBar {
                height: 18px;
                border: 1px solid #303846;
                border-radius: 9px;
                background: #1b2029;
                text-align: center;
                color: #e8edf5;
            }
            QProgressBar::chunk {
                background: #4f8cff;
                border-radius: 8px;
            }
            QTextEdit {
                background: #0b0e13;
                color: #b9c4d4;
                border: 1px solid #303846;
                border-radius: 8px;
                padding: 8px;
                font-family: monospace;
            }
            QPushButton {
                min-height: 38px;
                padding: 0 16px;
                border-radius: 8px;
                border: 1px solid #303846;
                background: #202632;
                color: #e8edf5;
            }
            QPushButton:hover {
                background: #2a3240;
            }
            QPushButton:disabled {
                color: #6f7888;
                background: #171b23;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        title = QLabel("PhoneView")
        title.setFont(QFont("Sans Serif", 28, QFont.Bold))
        root.addWidget(title)

        subtitle = QLabel("Preparing your Android connection environment")
        subtitle.setStyleSheet("color: #8e9aab; font-size: 14px;")
        root.addWidget(subtitle)

        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #181d26;
                border: 1px solid #2b3340;
                border-radius: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(10)

        self.step_label = QLabel("Step 1 of 2 — Checking dependencies")
        self.step_label.setStyleSheet("color: #9da9ba; font-size: 12px;")
        card_layout.addWidget(self.step_label)

        self.status = QLabel("Checking required components...")
        self.status.setFont(QFont("Sans Serif", 16, QFont.Bold))
        card_layout.addWidget(self.status)

        self.detail = QLabel("Scanning ADB, scrcpy and required system libraries.")
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color: #9da9ba;")
        card_layout.addWidget(self.detail)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        card_layout.addWidget(self.progress)

        self.progress_text = QLabel("Starting...")
        self.progress_text.setStyleSheet("color: #738094; font-size: 12px;")
        card_layout.addWidget(self.progress_text)

        root.addWidget(card)

        log_title = QLabel("Activity")
        log_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        root.addWidget(log_title)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(230)
        self.log.setPlaceholderText("Setup activity will appear here...")
        root.addWidget(self.log, 1)

        buttons = QHBoxLayout()
        self.install_button = QPushButton("Install missing components")
        self.install_button.clicked.connect(self.start_install)
        self.install_button.setEnabled(False)

        self.retry_button = QPushButton("Check again")
        self.retry_button.clicked.connect(self.run_check)

        self.continue_button = QPushButton("Continue to PhoneView")
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setEnabled(False)

        buttons.addWidget(self.install_button)
        buttons.addWidget(self.retry_button)
        buttons.addStretch(1)
        buttons.addWidget(self.continue_button)
        root.addLayout(buttons)

    def write_log(self, text):
        self.log.append(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def set_progress(self, value, text):
        self.progress.setValue(max(0, min(100, value)))
        self.progress_text.setText(text)

    def run_check(self):
        if self.process is not None:
            return

        self.install_phase = False
        self.step_label.setText("Step 1 of 2 — Checking dependencies")
        self.status.setText("Checking required components...")
        self.detail.setText("Scanning ADB, scrcpy and required system libraries.")
        self.set_progress(5, "Scanning system...")
        self.install_button.setEnabled(False)
        self.continue_button.setEnabled(False)

        items = self.checker.check()
        missing = [item for item in items if not item["ok"]]

        for item in items:
            state = "READY" if item["ok"] else "MISSING"
            self.write_log(f"[{state}] {item['name']}")

        if not missing:
            self.set_progress(100, "Everything is ready.")
            self.status.setText("Setup complete")
            self.detail.setText("All required components were found. PhoneView is ready to start.")
            self.install_button.setEnabled(False)
            self.continue_button.setEnabled(True)
            self.step_label.setText("Complete")
            return

        self.status.setText(f"{len(missing)} component(s) need attention")
        self.detail.setText("Some required components are missing. You can install them from this window.")
        self.set_progress(20, f"Found {len(missing)} missing component(s).")

        if self.can_auto_install():
            self.install_button.setEnabled(True)
            self.write_log("Ready to install missing Linux packages.")
        else:
            self.write_log(self.manual_install_message())

    def can_auto_install(self):
        return sys.platform.startswith("linux") and self.checker.command_exists("pkexec")

    def manual_install_message(self):
        if sys.platform.startswith("linux"):
            packages = self.checker.missing_linux_packages()
            return "Automatic installation requires pkexec. Install manually with: sudo apt install " + " ".join(packages)
        if sys.platform == "darwin":
            return "Install ADB and scrcpy with Homebrew, then click Check again."
        return "Install Android Platform Tools and scrcpy, then click Check again."

    def start_install(self):
        packages = self.checker.missing_linux_packages()
        if not packages:
            self.run_check()
            return

        self.install_phase = True
        self.install_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.step_label.setText("Step 2 of 2 — Installing dependencies")
        self.status.setText("Updating package information...")
        self.detail.setText("The system package manager is preparing the required components.")
        self.set_progress(30, "Running apt update...")
        self.write_log("Requesting administrator permission...")
        self.write_log("Starting: apt-get update")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.install_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.process.start("pkexec", ["apt-get", "update"])

    def read_output(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if data.strip():
            self.write_log(data.rstrip())
            if "Fetched" in data or "Reading package lists" in data:
                self.set_progress(max(self.progress.value(), 45), "Downloading and reading package lists...")

    def install_finished(self, exit_code, exit_status):
        self.read_output()

        if exit_code != 0:
            self.write_log(f"Package update failed (exit code {exit_code}).")
            self.status.setText("Package update failed")
            self.detail.setText("The system could not update its package information. Check the Activity log for details.")
            self.set_progress(30, "Update failed.")
            self.process = None
            self.retry_button.setEnabled(True)
            self.install_button.setEnabled(True)
            return

        self.write_log("Package lists updated successfully.")
        packages = self.checker.missing_linux_packages()
        self.status.setText("Installing missing components...")
        self.detail.setText("Downloading and installing: " + ", ".join(packages))
        self.set_progress(65, "Installing packages...")
        self.write_log("Starting: apt-get install -y " + " ".join(packages))

        try:
            self.process.finished.disconnect()
        except (TypeError, RuntimeError):
            pass

        self.process.finished.connect(self.package_install_finished)
        self.process.start("pkexec", ["apt-get", "install", "-y"] + packages)

    def package_install_finished(self, exit_code, exit_status):
        self.read_output()
        self.process = None
        self.retry_button.setEnabled(True)

        if exit_code != 0:
            self.status.setText("Installation failed")
            self.detail.setText("One or more components could not be installed. Read the Activity log, then try again.")
            self.write_log(f"Package installation failed (exit code {exit_code}).")
            self.set_progress(65, "Installation failed.")
            self.install_button.setEnabled(True)
            return

        self.set_progress(90, "Installation finished. Verifying...")
        self.status.setText("Verifying installation")
        self.detail.setText("Checking every dependency again before starting PhoneView.")
        self.write_log("Installation finished. Running final verification...")
        QTimer.singleShot(700, self.run_check)

    def process_error(self, error):
        self.write_log(f"Installer error: {error}")
        self.status.setText("Installer could not start")
        self.detail.setText("The system installer could not be started.")
        self.retry_button.setEnabled(True)
        self.install_button.setEnabled(True)
        self.process = None

    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process = None
        event.accept()

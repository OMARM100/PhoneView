import sys
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QVBoxLayout
from core.dependency_checker import DependencyChecker


class SetupWindow(QDialog):
    """First-run dependency checker/installer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PhoneView — Setup")
        self.resize(720, 500)
        self.checker = DependencyChecker()
        self.process = None
        self.build_ui()
        QTimer.singleShot(150, self.run_check)

    def build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("PhoneView Setup")
        title.setStyleSheet("font-size: 26px; font-weight: bold;")
        layout.addWidget(title)

        self.status = QLabel("Checking required components...")
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Setup log...")
        layout.addWidget(self.log)

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
        buttons.addWidget(self.continue_button)
        layout.addLayout(buttons)

    def write_log(self, text):
        self.log.append(text)

    def run_check(self):
        if self.process is not None:
            return

        self.progress.setValue(5)
        items = self.checker.check()
        missing = [item for item in items if not item["ok"]]

        for item in items:
            state = "OK" if item["ok"] else "MISSING"
            self.write_log(f"[{state}] {item['name']}")

        if not missing:
            self.progress.setValue(100)
            self.status.setText("All required components are ready.")
            self.install_button.setEnabled(False)
            self.continue_button.setEnabled(True)
            return

        self.status.setText(f"{len(missing)} component(s) missing.")
        self.progress.setValue(20)
        self.continue_button.setEnabled(False)

        if self.can_auto_install():
            self.install_button.setEnabled(True)
            self.write_log("PhoneView can install the missing Linux packages automatically.")
        else:
            self.install_button.setEnabled(False)
            self.write_log(self.manual_install_message())

    def can_auto_install(self):
        return sys.platform.startswith("linux") and self.checker.command_exists("pkexec")

    def manual_install_message(self):
        if sys.platform.startswith("linux"):
            packages = self.checker.missing_linux_packages()
            return (
                "Automatic installation requires pkexec. Install manually with: "
                + "sudo apt install " + " ".join(packages)
            )
        if sys.platform == "darwin":
            return "Install ADB and scrcpy with Homebrew, then click Check again."
        return "Install Android Platform Tools and scrcpy, then click Check again."

    def start_install(self):
        packages = self.checker.missing_linux_packages()
        if not packages:
            self.run_check()
            return

        self.install_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.continue_button.setEnabled(False)
        self.progress.setValue(30)
        self.status.setText("Updating package lists...")
        self.write_log("Requesting administrator permission...")

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

    def install_finished(self, exit_code, exit_status):
        self.read_output()
        if exit_code != 0:
            self.write_log(f"Package update failed (exit code {exit_code}).")
            self.status.setText("Package update failed.")
            self.progress.setValue(30)
            self.process = None
            self.retry_button.setEnabled(True)
            self.install_button.setEnabled(True)
            return

        self.write_log("Package lists updated. Installing missing packages...")
        self.progress.setValue(65)
        try:
            self.process.finished.disconnect()
        except (TypeError, RuntimeError):
            pass
        self.process.finished.connect(self.package_install_finished)
        self.process.start("pkexec", ["apt-get", "install", "-y"] + self.checker.missing_linux_packages())

    def package_install_finished(self, exit_code, exit_status):
        self.read_output()
        self.process = None
        self.retry_button.setEnabled(True)

        if exit_code != 0:
            self.status.setText("Some components could not be installed.")
            self.write_log(f"Package installation failed (exit code {exit_code}).")
            self.progress.setValue(65)
            self.install_button.setEnabled(True)
            return

        self.progress.setValue(90)
        self.status.setText("Verifying installation...")
        self.write_log("Installation finished. Verifying components...")
        QTimer.singleShot(500, self.run_check)

    def process_error(self, error):
        self.write_log(f"Installer error: {error}")
        self.status.setText("Could not start the system installer.")
        self.retry_button.setEnabled(True)
        self.install_button.setEnabled(True)
        self.process = None

    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process = None
        event.accept()

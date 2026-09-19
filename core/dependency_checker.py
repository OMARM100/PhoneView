import os
import shutil
import subprocess
import sys


class DependencyChecker:
    """Checks the external/runtime dependencies PhoneView needs."""

    def __init__(self):
        self.platform = sys.platform

    @staticmethod
    def command_exists(name: str) -> bool:
        return shutil.which(name) is not None

    @staticmethod
    def package_installed_debian(package: str) -> bool:
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", package],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def check(self):
        if self.platform.startswith("linux"):
            return [
                {"name": "ADB", "ok": self.command_exists("adb"), "package": "adb"},
                {"name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": "scrcpy"},
                {"name": "Qt XCB cursor support", "ok": self.package_installed_debian("libxcb-cursor0"), "package": "libxcb-cursor0"},
            ]
        if self.platform == "darwin":
            return [
                {"name": "ADB", "ok": self.command_exists("adb"), "package": "android-platform-tools"},
                {"name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": "scrcpy"},
            ]
        if os.name == "nt":
            return [
                {"name": "ADB", "ok": self.command_exists("adb"), "package": None},
                {"name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": None},
            ]
        return []

    def missing_linux_packages(self):
        return [item["package"] for item in self.check()
                if not item["ok"] and item.get("package")]

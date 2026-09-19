import os
import shutil
import subprocess
import sys


class DependencyChecker:
    """Detects the external components required by PhoneView."""

    def __init__(self):
        self.platform = sys.platform

    @staticmethod
    def command_exists(name: str) -> bool:
        return shutil.which(name) is not None

    @staticmethod
    def package_installed_debian(package: str) -> bool:
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", package],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "install ok installed" in result.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def check(self):
        if self.platform.startswith("linux"):
            return [
                {"id": "adb", "name": "Android Debug Bridge (ADB)", "ok": self.command_exists("adb"), "package": "adb"},
                {"id": "scrcpy", "name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": "scrcpy"},
                {
                    "id": "xcb",
                    "name": "Qt XCB cursor support",
                    "ok": self.package_installed_debian("libxcb-cursor0"),
                    "package": "libxcb-cursor0",
                },
            ]

        if self.platform == "darwin":
            return [
                {"id": "adb", "name": "Android Debug Bridge (ADB)", "ok": self.command_exists("adb"), "package": "android-platform-tools"},
                {"id": "scrcpy", "name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": "scrcpy"},
            ]

        if os.name == "nt":
            return [
                {"id": "adb", "name": "Android Debug Bridge (ADB)", "ok": self.command_exists("adb"), "package": None},
                {"id": "scrcpy", "name": "scrcpy", "ok": self.command_exists("scrcpy"), "package": None},
            ]

        return []

    def missing_linux_packages(self):
        return [
            item["package"]
            for item in self.check()
            if not item["ok"] and item.get("package")
        ]

    def has_missing(self):
        return any(not item["ok"] for item in self.check())

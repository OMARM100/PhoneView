import os
import re
import shutil
import subprocess
import sys

from core.scrcpy_installer import (
    PHONEVIEW_BUILD_NAME,
    PHONEVIEW_SCRCPY_VERSION,
    ScrcpyInstaller,
)


class DependencyChecker:
    """Detect required components and flag obsolete scrcpy installations."""

    MIN_SCRCPY_MAJOR = 4

    def __init__(self):
        self.platform = sys.platform

    @staticmethod
    def command_exists(name: str) -> bool:
        if name == "scrcpy":
            return ScrcpyInstaller.find_binary() is not None
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

    @staticmethod
    def scrcpy_version():
        try:
            output = ScrcpyInstaller.version()
            match = re.search(r"scrcpy\s+(\d+)\.(\d+)", output, re.IGNORECASE)
            return (int(match.group(1)), int(match.group(2))) if match else None
        except (OSError, subprocess.SubprocessError):
            return None

    def scrcpy_ok(self):
        return ScrcpyInstaller.is_phoneview_build()

    def check(self):
        if self.platform.startswith("linux"):
            return [
                {
                    "id": "adb",
                    "name": "Android Debug Bridge (ADB)",
                    "ok": self.command_exists("adb"),
                    "package": "adb",
                },
                {
                    "id": "scrcpy",
                    "name": f"PhoneView scrcpy engine ({PHONEVIEW_SCRCPY_VERSION})",
                    "ok": self.scrcpy_ok(),
                    "package": "phoneview-scrcpy",
                },
                {
                    "id": "xcb",
                    "name": "Qt XCB cursor support",
                    "ok": self.package_installed_debian("libxcb-cursor0"),
                    "package": "libxcb-cursor0",
                },
                {
                    "id": "wmctrl",
                    "name": "X11 window control (wmctrl)",
                    "ok": self.command_exists("wmctrl"),
                    "package": "wmctrl",
                },
                {
                    "id": "xdotool",
                    "name": "X11 input/window helper (xdotool)",
                    "ok": self.command_exists("xdotool"),
                    "package": "xdotool",
                },
            ]

        if self.platform == "darwin":
            return [
                {
                    "id": "adb",
                    "name": "Android Debug Bridge (ADB)",
                    "ok": self.command_exists("adb"),
                    "package": "android-platform-tools",
                },
                {
                    "id": "scrcpy",
                    "name": "scrcpy (current release)",
                    "ok": self.scrcpy_ok(),
                    "package": "scrcpy",
                },
            ]

        if os.name == "nt":
            return [
                {
                    "id": "adb",
                    "name": "Android Debug Bridge (ADB)",
                    "ok": self.command_exists("adb"),
                    "package": None,
                },
                {
                    "id": "scrcpy",
                    "name": "scrcpy (current release)",
                    "ok": self.scrcpy_ok(),
                    "package": None,
                },
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

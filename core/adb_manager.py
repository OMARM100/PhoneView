import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class AndroidDevice:
    serial: str
    state: str
    model: str = ""
    product: str = ""


class ADBManager:
    def __init__(self):
        self.adb = self._find_executable("adb")
        self.server_started = False

    @staticmethod
    def _find_executable(name: str):
        exe = shutil.which(name)
        if exe:
            return exe

        if os.name == "nt":
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
            ]
        else:
            candidates = [
                os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
                "/opt/android-sdk/platform-tools/adb",
                "/usr/bin/adb",
            ]

        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def available(self):
        return bool(self.adb)

    def start_server(self):
        if not self.adb:
            return False, "ADB is not installed or not in PATH."

        if self.server_started:
            return True, "ADB server already started."

        try:
            result = subprocess.run(
                [self.adb, "start-server"],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)

        if result.returncode != 0:
            return False, (result.stderr or result.stdout).strip()

        self.server_started = True
        return True, (result.stdout or result.stderr or "ADB server started").strip()

    def devices(self):
        if not self.adb:
            return []

        try:
            result = subprocess.run(
                [self.adb, "devices", "-l"],
                capture_output=True,
                text=True,
                timeout=4,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if result.returncode != 0:
            return []

        devices = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices attached"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            serial, state = parts[0], parts[1]
            model = ""
            product = ""

            for item in parts[2:]:
                if item.startswith("model:"):
                    model = item[6:].replace("_", " ")
                elif item.startswith("product:"):
                    product = item[8:].replace("_", " ")

            devices.append(AndroidDevice(serial, state, model, product))

        return devices

    def shell(self, serial, *args, timeout=8):
        if not self.adb:
            raise RuntimeError("ADB is not available.")

        return subprocess.run(
            [self.adb, "-s", serial, "shell", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def device_info(self, serial):
        def prop(name):
            result = self.shell(serial, "getprop", name)
            return result.stdout.strip() if result.returncode == 0 else ""

        return {
            "model": prop("ro.product.model"),
            "brand": prop("ro.product.brand"),
            "android": prop("ro.build.version.release"),
            "sdk": prop("ro.build.version.sdk"),
        }

    def is_device_ready(self, serial):
        return any(d.serial == serial and d.state == "device" for d in self.devices())

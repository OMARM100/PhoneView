import os
import shutil
import subprocess
from dataclasses import dataclass

@dataclass
class AndroidDevice:
    serial: str
    state: str
    model: str = ""

class ADBManager:
    def __init__(self):
        self.adb = self._find_executable("adb")

    @staticmethod
    def _find_executable(name: str):
        exe = shutil.which(name)
        if exe:
            return exe
        if os.name == "nt":
            for path in [
                os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
            ]:
                if os.path.isfile(path):
                    return path
        else:
            for path in [
                os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
                "/opt/android-sdk/platform-tools/adb",
            ]:
                if os.path.isfile(path):
                    return path
        return None

    def available(self):
        return bool(self.adb)

    def start_server(self):
        if not self.adb:
            return False, "ADB غير موجود في PATH."
        try:
            p = subprocess.run([self.adb, "start-server"], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return False, str(e)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout).strip()
        return True, (p.stdout or "ADB server started").strip()

    def devices(self):
        if not self.adb:
            return []
        try:
            p = subprocess.run([self.adb, "devices", "-l"], capture_output=True, text=True, timeout=10)
        except Exception:
            return []
        result = []
        for line in p.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices attached"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            model = ""
            for item in parts[2:]:
                if item.startswith("model:"):
                    model = item[6:].replace("_", " ")
            result.append(AndroidDevice(serial, state, model))
        return result

    def shell(self, serial, *args):
        return subprocess.run(
            [self.adb, "-s", serial, "shell", *args],
            capture_output=True, text=True, timeout=10
        )

    def device_info(self, serial):
        return {
            "model": self.shell(serial, "getprop", "ro.product.model").stdout.strip(),
            "brand": self.shell(serial, "getprop", "ro.product.brand").stdout.strip(),
            "android": self.shell(serial, "getprop", "ro.build.version.release").stdout.strip(),
        }

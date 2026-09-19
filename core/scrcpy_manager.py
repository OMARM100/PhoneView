import os
import shutil
import subprocess

class ScrcpyManager:
    def __init__(self):
        self.process = None
        self.scrcpy = self._find_scrcpy()

    @staticmethod
    def _find_scrcpy():
        exe = shutil.which("scrcpy")
        if exe:
            return exe
        if os.name == "nt":
            candidates = [
                os.path.expandvars(r"%ProgramFiles%\scrcpy\scrcpy.exe"),
                os.path.expandvars(r"%USERPROFILE%\scoop\apps\scrcpy\current\scrcpy.exe"),
            ]
        else:
            candidates = [
                "/usr/bin/scrcpy",
                "/usr/local/bin/scrcpy",
                os.path.expanduser("~/bin/scrcpy"),
            ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def available(self):
        return bool(self.scrcpy)

    def start(self, serial):
        self.stop()
        if not self.scrcpy:
            raise RuntimeError("scrcpy غير موجود. ثبّت scrcpy ثم أعد المحاولة.")
        cmd = [
            self.scrcpy, "--serial", serial,
            "--window-title", "PhoneView - Android",
            "--stay-awake", "--no-audio",
            "--max-size", "1280", "--video-bit-rate", "8M"
        ]
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
            self.process = None

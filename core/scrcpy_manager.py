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
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return None

    def available(self):
        return bool(self.scrcpy)

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, serial):
        self.stop()

        if not self.scrcpy:
            raise RuntimeError(
                "scrcpy is not installed or not available in PATH."
            )

        cmd = [
            self.scrcpy,
            "--serial", serial,
            "--window-title", "PhoneView - Android",
            "--no-audio",
            "--stay-awake",
            "--max-size", "1280",
            "--video-bit-rate", "8M",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self.process = None
            raise RuntimeError(f"Could not start scrcpy: {exc}") from exc

        # scrcpy exits immediately when ADB/device access fails.
        try:
            code = self.process.wait(timeout=0.35)
        except subprocess.TimeoutExpired:
            return

        output = ""
        try:
            output = self.process.stdout.read().strip() if self.process.stdout else ""
        except Exception:
            pass

        self.process = None
        detail = output[-1200:] if output else f"scrcpy exited with code {code}."
        raise RuntimeError(detail)

    def read_output(self):
        if not self.process or not self.process.stdout:
            return ""
        try:
            return self.process.stdout.read()
        except Exception:
            return ""

    def stop(self):
        process = self.process
        self.process = None

        if process is None:
            return

        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        try:
            if process.stdout:
                process.stdout.close()
        except Exception:
            pass

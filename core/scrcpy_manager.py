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

    def version(self):
        if not self.scrcpy:
            return ""
        try:
            result = subprocess.run(
                [self.scrcpy, "--version"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return (result.stdout or result.stderr).splitlines()[0].strip()
        except Exception:
            return ""

    def running(self):
        return self.process is not None and self.process.poll() is None

    def _build_command(self, serial):
        # Keep the launch command compatible with scrcpy 1.25.
        # Avoid newer options such as --no-audio, --video-bit-rate,
        # and --max-size because option names/support vary by scrcpy release.
        return [
            self.scrcpy,
            "--serial", serial,
            "--window-title", "PhoneView - Android",
            "--stay-awake",
        ]

    def start(self, serial):
        self.stop()

        if not self.scrcpy:
            raise RuntimeError("scrcpy is not installed or cannot be found in PATH.")

        cmd = self._build_command(serial)

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

        try:
            self.process.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            return

        output = ""
        try:
            output = self.process.stdout.read().strip() if self.process.stdout else ""
        except Exception:
            pass

        code = self.process.returncode
        self.process = None
        detail = output[-2000:] if output else f"scrcpy exited with code {code}."
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

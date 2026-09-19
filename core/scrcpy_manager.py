import os
import shutil
import subprocess
import sys


class ScrcpyManager:
    """Launch and monitor scrcpy across desktop platforms."""

    def __init__(self):
        self.process = None
        self.scrcpy = self._find_scrcpy()
        self._help_text = None
        self.last_output = ""

    @staticmethod
    def _find_scrcpy():
        exe = shutil.which("scrcpy")
        if exe:
            return exe

        if os.name == "nt":
            candidates = [
                os.path.expandvars(r"%ProgramFiles%\scrcpy\scrcpy.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\scrcpy\scrcpy.exe"),
                os.path.expandvars(r"%USERPROFILE%\scoop\apps\scrcpy\current\scrcpy.exe"),
            ]
        else:
            candidates = [
                "/usr/bin/scrcpy",
                "/usr/local/bin/scrcpy",
                os.path.expanduser("~/bin/scrcpy"),
                "/snap/bin/scrcpy",
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
            text = (result.stdout or result.stderr or "").strip()
            return text.splitlines()[0] if text else ""
        except Exception:
            return ""

    def _help(self):
        if self._help_text is not None:
            return self._help_text
        if not self.scrcpy:
            self._help_text = ""
            return self._help_text
        try:
            result = subprocess.run(
                [self.scrcpy, "--help"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            self._help_text = (result.stdout or "") + "\n" + (result.stderr or "")
        except Exception:
            self._help_text = ""
        return self._help_text

    def _supports(self, option):
        return option in self._help()

    def _build_command(self, serial):
        # Start with options known to work on scrcpy 1.25.
        cmd = [self.scrcpy, "-s", serial]

        if self._supports("--stay-awake"):
            cmd.append("--stay-awake")

        if self._supports("--window-title"):
            cmd += ["--window-title", "PhoneView - Android"]

        # Keep the mirror window visible when PhoneView starts it.
        if self._supports("--always-on-top"):
            cmd.append("--always-on-top")

        if self._supports("--window-width") and self._supports("--window-height"):
            cmd += ["--window-width", "420", "--window-height", "700"]

        return cmd

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, serial):
        self.stop()
        self.last_output = ""

        if not self.scrcpy:
            raise RuntimeError("scrcpy is not installed or cannot be found in PATH.")

        env = os.environ.copy()
        if os.name != "nt" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "No graphical display session was found. Start PhoneView from your desktop session."
            )

        cmd = self._build_command(serial)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                start_new_session=(os.name != "nt"),
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
            )
        except OSError as exc:
            self.process = None
            raise RuntimeError(f"Could not start scrcpy: {exc}") from exc

        # scrcpy creates its SDL window asynchronously. Wait only for an
        # immediate startup failure; do not block until the mirror closes.
        try:
            self.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return True

        self._collect_output()
        code = self.process.returncode
        self.process = None
        detail = self.last_output[-3000:] if self.last_output else f"scrcpy exited with code {code}."
        raise RuntimeError(detail)

    def _collect_output(self):
        if not self.process or not self.process.stdout:
            return
        try:
            data = self.process.stdout.read()
            if data:
                self.last_output = data.strip()
        except Exception:
            pass

    def read_output(self):
        if not self.process or not self.process.stdout:
            return ""
        try:
            data = self.process.stdout.read()
            if data:
                self.last_output = data.strip()
            return data
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

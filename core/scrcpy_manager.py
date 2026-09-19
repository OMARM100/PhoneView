import os
import shutil
import subprocess
import tempfile


class ScrcpyManager:
    """Launch and monitor scrcpy without blocking its output pipe."""

    def __init__(self):
        self.process = None
        self.scrcpy = self._find_scrcpy()
        self._help_text = None
        self.last_output = ""
        self._log_file = None
        self._log_path = None

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
            result = subprocess.run([self.scrcpy, "--version"], capture_output=True, text=True, timeout=3)
            output = (result.stdout or result.stderr or "").strip()
            return output.splitlines()[0] if output else ""
        except Exception:
            return ""

    def _help(self):
        if self._help_text is not None:
            return self._help_text
        if not self.scrcpy:
            self._help_text = ""
            return ""
        try:
            result = subprocess.run([self.scrcpy, "--help"], capture_output=True, text=True, timeout=3)
            self._help_text = (result.stdout or "") + "\n" + (result.stderr or "")
        except Exception:
            self._help_text = ""
        return self._help_text

    def _supports(self, option):
        return option in self._help()

    def _build_command(self, serial):
        cmd = [self.scrcpy, "-s", serial, "--window-title", "PhoneView - Android"]

        if self._supports("--stay-awake"):
            cmd.append("--stay-awake")
        if self._supports("--window-width"):
            cmd += ["--window-width", "420"]
        if self._supports("--window-height"):
            cmd += ["--window-height", "700"]
        if self._supports("--always-on-top"):
            cmd.append("--always-on-top")

        return cmd

    def running(self):
        return self.process is not None and self.process.poll() is None

    def _open_log(self):
        self._cleanup_log()
        self._log_file = tempfile.NamedTemporaryFile(
            mode="w+", encoding="utf-8", prefix="phoneview_scrcpy_", suffix=".log", delete=False
        )
        self._log_path = self._log_file.name

    def _read_log(self):
        if not self._log_path:
            return ""
        try:
            with open(self._log_path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read().strip()
        except Exception:
            return ""

    def _cleanup_log(self):
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
        self._log_file = None

        if self._log_path:
            try:
                os.remove(self._log_path)
            except OSError:
                pass
        self._log_path = None

    def start(self, serial):
        self.stop()
        self.last_output = ""

        if not self.scrcpy:
            raise RuntimeError("scrcpy is not installed or cannot be found in PATH.")

        env = os.environ.copy()
        if os.name != "nt" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            raise RuntimeError("No graphical display session was found. Start PhoneView from your desktop session.")

        self._open_log()

        try:
            self.process = subprocess.Popen(
                self._build_command(serial),
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=(os.name != "nt"),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        except OSError as exc:
            self.process = None
            self.last_output = str(exc)
            self._cleanup_log()
            raise RuntimeError(f"Could not start scrcpy: {exc}") from exc

        try:
            self.process.wait(timeout=1.2)
        except subprocess.TimeoutExpired:
            return True

        self.last_output = self._read_log()
        code = self.process.returncode
        self.process = None
        self._cleanup_log()
        raise RuntimeError(self.last_output[-4000:] if self.last_output else f"scrcpy exited immediately with code {code}.")

    def read_output(self):
        output = self._read_log()
        if output:
            self.last_output = output
        return output

    def stop(self):
        process = self.process
        self.process = None

        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=1)
                except Exception:
                    pass

        output = self._read_log()
        if output:
            self.last_output = output

        self._cleanup_log()

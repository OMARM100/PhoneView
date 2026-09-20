import os
import re
import shutil
import subprocess
import tempfile

from core.scrcpy_installer import ScrcpyInstaller


class ScrcpyManager:
    """Launch and monitor scrcpy, including compatibility diagnostics."""

    MIN_RECOMMENDED_MAJOR = 2

    def __init__(self):
        self.process = None
        self.scrcpy = self._find_scrcpy()
        self._help_text = None
        self.last_output = ""
        self._log_file = None
        self._log_path = None

    @staticmethod
    def _find_scrcpy():
        # PhoneView intentionally uses only its pinned patched scrcpy build.
        return ScrcpyInstaller.local_binary()

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
            output = (result.stdout or result.stderr or "").strip()
            return output.splitlines()[0] if output else ""
        except Exception:
            return ""

    def version_number(self):
        # scrcpy 1.25 -> (1, 25)
        match = re.search(r"scrcpy\s+(\d+)\.(\d+)", self.version(), re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def is_legacy(self):
        number = self.version_number()
        return number is not None and number[0] < self.MIN_RECOMMENDED_MAJOR

    def compatibility_message(self):
        version = self.version() or "unknown"
        return (
            f"Installed scrcpy: {version}. "
            "This is a legacy scrcpy release and may not work with newer Android versions. "
            "PhoneView requires a current scrcpy release for reliable screen mirroring."
        )

    def _help(self):
        if self._help_text is not None:
            return self._help_text
        if not self.scrcpy:
            self._help_text = ""
            return ""
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

    def _build_command(self, serial, project_name="Android Project"):
        cmd = [
            self.scrcpy,
            "-s",
            serial,
            "--window-title",
            " ".join(str(project_name).split()).strip()[:80] or "Android Project",
        ]

        if self._supports("--stay-awake"):
            cmd.append("--stay-awake")

        # PhoneView owns the native window size. Do not force a fixed
        # portrait 520x820 window onto devices whose video is landscape.
        if self._supports("--always-on-top"):
            cmd.append("--always-on-top")

        return cmd

    def running(self):
        return self.process is not None and self.process.poll() is None

    def _open_log(self):
        self._cleanup_log()
        self._log_file = tempfile.NamedTemporaryFile(
            mode="w+",
            encoding="utf-8",
            prefix="phoneview_scrcpy_",
            suffix=".log",
            delete=False,
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

    def start(self, serial, project_name="Android Project"):
        self.stop()
        self.last_output = ""

        if not self.scrcpy:
            raise RuntimeError("scrcpy is not installed or cannot be found in PATH.")

        env = ScrcpyInstaller.runtime_environment()
        # Always inject the bundled SDL3 directory explicitly for the child
        # process. This also protects against launchers/symlinks started
        # outside PhoneView's Python environment.
        lib_dir = ScrcpyInstaller.runtime_library_dir()
        if lib_dir:
            old_ld = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{lib_dir}:{old_ld}" if old_ld else lib_dir
        env["PHONEVIEW_MAPPING"] = "1"
        if os.name != "nt" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "No graphical display session was found. Start PhoneView from the desktop session."
            )


        self._open_log()

        try:
            self.process = subprocess.Popen(
                self._build_command(serial, project_name),
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
            self.process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            return True

        self.last_output = self._read_log()
        code = self.process.returncode
        self.process = None
        self._cleanup_log()
        raise RuntimeError(
            self.last_output[-5000:]
            if self.last_output
            else f"scrcpy exited immediately with code {code}."
        )

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


    def window_exists(self, title):
        """Return True when a native scrcpy window with the requested title exists."""
        title = str(title or "").strip()
        if not title:
            return False

        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    candidate = line.split(None, 3)[-1].strip() if line.split(None, 3) else ""
                    if candidate == title or title in candidate or candidate in title:
                        return True
        except (OSError, subprocess.SubprocessError):
            pass

        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return False

    def focus_window(self, title):
        """Best-effort focus for the unified PhoneView native window."""
        title = "PhoneView"
        if os.name == "nt":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, title)
                if hwnd:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    return True
            except Exception:
                return False
        if os.name != "nt":
            for command in (["wmctrl", "-a", title], ["xdotool", "search", "--name", title, "windowactivate"]):
                try:
                    result = subprocess.run(command, capture_output=True, timeout=2)
                    if result.returncode == 0:
                        return True
                except (OSError, subprocess.SubprocessError):
                    pass
        return False

    def adb_keyevent(self, serial, keycode):
        if not serial:
            raise RuntimeError("No Android device is selected.")
        result = subprocess.run(
            ["adb", "-s", serial, "shell", "input", "keyevent", str(keycode)],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "ADB key event failed.").strip())
        return True

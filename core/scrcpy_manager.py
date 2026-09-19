import os
import shutil
import subprocess


class ScrcpyManager:
    """Launch and control scrcpy across desktop platforms."""

    def __init__(self):
        self.process = None
        self.scrcpy = self._find_scrcpy()
        self._help_text = None

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
        elif sys_platform := __import__("sys").platform:
            candidates = [
                "/usr/bin/scrcpy",
                "/usr/local/bin/scrcpy",
                os.path.expanduser("~/bin/scrcpy"),
                "/snap/bin/scrcpy",
            ]
        else:
            candidates = []

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
        # Start with the most conservative options so old scrcpy releases
        # such as Ubuntu's 1.25 remain supported.
        cmd = [self.scrcpy, "-s", serial]

        help_text = self._help()

        if "--stay-awake" in help_text:
            cmd.append("--stay-awake")

        if "--window-title" in help_text:
            cmd += ["--window-title", "PhoneView - Android"]

        # Give the SDL window a predictable initial size when supported.
        if "--window-width" in help_text and "--window-height" in help_text:
            cmd += ["--window-width", "720", "--window-height", "1280"]

        return cmd

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, serial):
        self.stop()

        if not self.scrcpy:
            raise RuntimeError("scrcpy is not installed or cannot be found in PATH.")

        cmd = self._build_command(serial)

        env = os.environ.copy()

        # Do not force a video driver: inherit the user's graphical desktop.
        # This keeps X11/Wayland selection under SDL's control.
        if os.name != "nt" and not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            raise RuntimeError(
                "No graphical display session was found. Start PhoneView from your desktop session."
            )

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                start_new_session=(os.name != "nt"),
                creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
            )
        except OSError as exc:
            self.process = None
            raise RuntimeError(f"Could not start scrcpy: {exc}") from exc

        # scrcpy normally creates its SDL window asynchronously. Only treat
        # it as a failure if the process actually exits during startup.
        try:
            self.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return True

        output = ""
        try:
            output = self.process.stdout.read().strip() if self.process.stdout else ""
        except Exception:
            pass

        code = self.process.returncode
        self.process = None
        detail = output[-3000:] if output else f"scrcpy exited with code {code}."
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

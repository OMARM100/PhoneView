import os
import subprocess
import sys


def _restart_inside_project_venv():
    """Run PhoneView with the project's virtual environment automatically."""
    if os.environ.get("PHONEVIEW_VENV_BOOTSTRAPPED") == "1":
        return

    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(project_dir, ".venv")

    if os.name == "nt":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    current_python = os.path.abspath(sys.executable)
    target_python = os.path.abspath(venv_python)

    if current_python == target_python:
        return

    if not os.path.exists(target_python):
        print("PhoneView: creating project virtual environment...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "venv", venv_dir],
                cwd=project_dir,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"PhoneView: could not create .venv: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    requirements = os.path.join(project_dir, "requirements.txt")
    try:
        probe = subprocess.run(
            [target_python, "-c", "import PySide6"],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        probe = None

    if probe is None or probe.returncode != 0:
        print("PhoneView: installing Python dependencies...")
        try:
            subprocess.check_call(
                [target_python, "-m", "pip", "install", "-r", requirements],
                cwd=project_dir,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(
                f"PhoneView: could not install Python dependencies: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(1) from exc

    env = os.environ.copy()
    env["PHONEVIEW_VENV_BOOTSTRAPPED"] = "1"

    try:
        os.execve(target_python, [target_python, *sys.argv], env)
    except OSError as exc:
        print(f"PhoneView: could not start .venv Python: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


_restart_inside_project_venv()

from PySide6.QtWidgets import QApplication

from core.dependency_checker import DependencyChecker
from ui.setup_window import SetupWindow
from ui.main_window import MainWindow


def main():
    # scrcpy is embedded as a native child window. On Linux Wayland sessions,
    # use XWayland/XCB when available so Qt and scrcpy share the same windowing
    # backend. On normal X11 sessions this does nothing.
    if sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland":
        if os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)
    app.setApplicationName("PhoneView")

    # Do not show the setup window when the environment is already complete.
    checker = DependencyChecker()
    if checker.has_missing():
        setup = SetupWindow()
        if setup.exec() != SetupWindow.Accepted:
            return

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

import os
import sys
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

import sys
from PySide6.QtWidgets import QApplication

from core.dependency_checker import DependencyChecker
from ui.setup_window import SetupWindow
from ui.main_window import MainWindow


def main():
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

import sys
from PySide6.QtWidgets import QApplication

from ui.setup_window import SetupWindow
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PhoneView")

    setup = SetupWindow()
    if setup.exec() != SetupWindow.Accepted:
        return

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

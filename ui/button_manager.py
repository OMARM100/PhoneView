from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ButtonManagerDialog(QDialog):
    """Simple keyboard/button manager. Actions are intentionally prepared for the next phase."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Button Manager")
        self.setMinimumSize(620, 470)
        self.setModal(False)

        self.setStyleSheet(
            """
            QDialog, QWidget {
                background: #0A0E14;
                color: #F4F7FB;
                font-family: "DejaVu Sans", "Noto Sans", sans-serif;
            }
            QFrame#Card {
                background: #10151D;
                border: 1px solid #202A37;
                border-radius: 16px;
            }
            QLabel#Title { font-size: 20px; font-weight: 900; }
            QLabel#Muted { color: #7E8B9D; font-size: 10px; }
            QLabel#Key {
                background: #172235;
                border: 1px solid #29476D;
                border-radius: 7px;
                padding: 5px 9px;
                color: #78A9FF;
                font-weight: 900;
            }
            QListWidget {
                background: #090D13;
                border: 1px solid #202A37;
                border-radius: 12px;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 8px;
            }
            QListWidget::item:selected { background: #14223A; }
            QLineEdit {
                background: #0B1017;
                border: 1px solid #293443;
                border-radius: 9px;
                padding: 9px 10px;
                color: #FFFFFF;
            }
            QPushButton {
                min-height: 36px;
                padding: 0 14px;
                border-radius: 9px;
                border: 1px solid #293443;
                background: #171D26;
                color: #CAD3DE;
                font-weight: 800;
            }
            QPushButton:hover { background: #222B37; color: #FFFFFF; }
            QPushButton#Primary {
                background: #2D73E5;
                border-color: #2D73E5;
                color: #FFFFFF;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Button Manager")
        title.setObjectName("Title")
        title_box.addWidget(title)
        subtitle = QLabel("Create keyboard buttons now. Actions will be connected to Android controls next.")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        shortcut = QLabel("CTRL + B")
        shortcut.setObjectName("Key")
        header.addWidget(shortcut, 0, Qt.AlignTop)
        root.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.setSpacing(9)

        self.list = QListWidget()
        cl.addWidget(self.list, 1)

        form = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Button name, e.g. Home")
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Shortcut, e.g. F1")
        form.addWidget(self.name_input, 2)
        form.addWidget(self.key_input, 1)
        cl.addLayout(form)

        actions = QHBoxLayout()
        add = QPushButton("+ Add Button")
        add.setObjectName("Primary")
        add.clicked.connect(self.add_button)
        actions.addWidget(add)

        remove = QPushButton("Remove Selected")
        remove.clicked.connect(self.remove_selected)
        actions.addWidget(remove)
        actions.addStretch()

        close = QPushButton("Close")
        close.clicked.connect(self.close)
        actions.addWidget(close)
        cl.addLayout(actions)

        root.addWidget(card, 1)

        self.add_row("Home", "HOME")
        self.add_row("Back", "ESC")
        self.add_row("Refresh", "F5")

    def add_row(self, name, key):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, {"name": name, "key": key})
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 4, 10, 4)
        label = QLabel(name)
        label.setStyleSheet("font-weight:800;")
        layout.addWidget(label, 1)
        key_label = QLabel(key)
        key_label.setObjectName("Key")
        layout.addWidget(key_label)
        action = QLabel("Ready")
        action.setObjectName("Muted")
        layout.addWidget(action)
        item.setSizeHint(row.sizeHint())
        self.list.addItem(item)
        self.list.setItemWidget(item, row)

    def add_button(self):
        name = self.name_input.text().strip()
        key = self.key_input.text().strip().upper()
        if not name or not key:
            QMessageBox.information(self, "Button Manager", "Enter a button name and keyboard shortcut.")
            return

        for i in range(self.list.count()):
            data = self.list.item(i).data(Qt.UserRole) or {}
            if data.get("key") == key:
                QMessageBox.warning(self, "Button Manager", f"The shortcut {key} is already assigned.")
                return

        self.add_row(name, key)
        self.name_input.clear()
        self.key_input.clear()
        self.name_input.setFocus()

    def remove_selected(self):
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)

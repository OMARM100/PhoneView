import re
import sys

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.dependency_checker import DependencyChecker


PHONEVIEW_QSS = """
QDialog {
    background: #0B0D10;
    color: #E8EDF5;
    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
}
QLabel { color: #E8EDF5; background: transparent; }
QLabel#Eyebrow { color: #6E9BFF; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
QLabel#Subtitle { color: #7F8998; font-size: 10px; }
QLabel#Muted { color: #778292; font-size: 9px; }
QLabel#StatusTitle { color: #F4F7FB; font-size: 17px; font-weight: 800; }
QLabel#StatusDetail { color: #8994A5; font-size: 10px; }
QLabel#Percent { color: #6E9BFF; font-size: 18px; font-weight: 800; }
QLabel#SectionTitle { color: #DCE3ED; font-size: 10px; font-weight: 800; }
QLabel#SectionMeta { color: #667181; font-size: 9px; }
QFrame#TopLine { background: #1B5EFF; border-radius: 2px; }
QFrame#StatusCard {
    background: #13171D;
    border: 1px solid #222A34;
    border-radius: 18px;
}
QFrame#StatusGlow {
    background: #13264A;
    border: none;
    border-radius: 9px;
}
QFrame#Card {
    background: #11151A;
    border: 1px solid #202832;
    border-radius: 16px;
}
QFrame#DependencyRow {
    background: #151A20;
    border: 1px solid #222A34;
    border-radius: 11px;
}
QFrame#DependencyRow:hover {
    background: #181F27;
    border-color: #2C3745;
}
QLabel#DependencyName { color: #DCE3ED; font-size: 10px; font-weight: 700; }
QLabel#DependencyState { color: #7F8998; font-size: 9px; font-weight: 800; }
QLabel#StatusIcon {
    background: #202833;
    color: #7F8998;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 800;
}
QProgressBar {
    background: #202731;
    border: none;
    border-radius: 4px;
    min-height: 7px;
    max-height: 7px;
}
QProgressBar::chunk { background: #397BFF; border-radius: 4px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #303A47; min-height: 22px; border-radius: 2px; }
QScrollBar::handle:vertical:hover { background: #465365; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTextEdit#ActivityLog {
    background: #0A0D10;
    color: #98A5B6;
    border: 1px solid #202832;
    border-radius: 13px;
    padding: 10px;
    font-family: "DejaVu Sans Mono", "Noto Sans Mono", monospace;
    font-size: 9px;
    selection-background-color: #245FCA;
    selection-color: #FFFFFF;
}
QPushButton {
    min-height: 34px;
    padding: 0 14px;
    border-radius: 9px;
    border: 1px solid #2A333F;
    background: #171C22;
    color: #C8D0DB;
    font-size: 9px;
    font-weight: 800;
}
QPushButton:hover { background: #202731; border-color: #384454; color: #F0F4F8; }
QPushButton:pressed { background: #11151A; }
QPushButton:disabled { background: #14181D; border-color: #1D242D; color: #4F5967; }
QPushButton#Primary {
    background: #2D6BEF;
    border-color: #2D6BEF;
    color: #FFFFFF;
    min-width: 138px;
}
QPushButton#Primary:hover { background: #4380FF; border-color: #4380FF; }
QPushButton#Primary:pressed { background: #2459C7; }
QPushButton#Primary:disabled { background: #172C50; border-color: #172C50; color: #526B91; }
QPushButton#Quiet {
    background: transparent;
    border-color: transparent;
    color: #7E8999;
}
QPushButton#Quiet:hover { background: #171C22; border-color: #252E39; color: #D4DCE7; }
"""

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 19, 22, 17)
        root.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setSpacing(12)

        brand = QVBoxLayout()
        brand.setSpacing(2)

        eyebrow = QLabel("PHONEVIEW  /  ANDROID DESKTOP CLIENT")
        eyebrow.setObjectName("Eyebrow")
        brand.addWidget(eyebrow)

        title = QLabel("PhoneView")
        title.setFont(QFont("DejaVu Sans", 23, QFont.Bold))
        brand.addWidget(title)

        subtitle = QLabel("Secure first-run environment setup")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        brand.addWidget(subtitle)

        header.addLayout(brand, 1)

        badge = QLabel("FIRST RUN")
        badge.setObjectName("Muted")
        badge.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(badge)

        root.addLayout(header)

        # Main status
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(10)

        line = QFrame()
        line.setObjectName("TopLine")
        line.setFixedHeight(4)
        status_layout.addWidget(line)

        status_row = QHBoxLayout()
        status_row.setSpacing(14)

        glow = QFrame()
        glow.setObjectName("StatusGlow")
        glow.setFixedSize(42, 42)
        glow_layout = QVBoxLayout(glow)
        glow_layout.setContentsMargins(0, 0, 0, 0)
        self.status_icon = QLabel("●")
        self.status_icon.setAlignment(Qt.AlignCenter)
        self.status_icon.setStyleSheet("color:#5B8FFF; font-size:15px;")
        glow_layout.addWidget(self.status_icon)
        status_row.addWidget(glow)

        status_text = QVBoxLayout()
        status_text.setSpacing(3)

        self.status = QLabel("Checking your system...")
        self.status.setObjectName("StatusTitle")
        self.status.setWordWrap(True)
        status_text.addWidget(self.status)

        self.detail = QLabel("Detecting ADB, scrcpy and required system libraries.")
        self.detail.setObjectName("StatusDetail")
        self.detail.setWordWrap(True)
        status_text.addWidget(self.detail)

        status_row.addLayout(status_text, 1)

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Percent")
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        status_row.addWidget(self.percent_label)

        status_layout.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        status_layout.addWidget(self.progress)

        self.progress_text = QLabel("Initializing setup...")
        self.progress_text.setObjectName("Muted")
        self.progress_text.setWordWrap(True)
        status_layout.addWidget(self.progress_text)

        root.addWidget(status_card)

        # Dependencies card
        dependencies = QFrame()
        dependencies.setObjectName("Card")
        dep_layout = QVBoxLayout(dependencies)
        dep_layout.setContentsMargins(14, 12, 14, 12)
        dep_layout.setSpacing(8)

        dep_header = QHBoxLayout()
        dep_title = QLabel("Required components")
        dep_title.setObjectName("SectionTitle")
        dep_header.addWidget(dep_title)
        dep_header.addStretch(1)

        dep_hint = QLabel("3 COMPONENTS")
        dep_hint.setObjectName("SectionMeta")
        dep_header.addWidget(dep_hint)
        dep_layout.addLayout(dep_header)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        component_layout = QVBoxLayout(content)
        component_layout.setContentsMargins(0, 0, 0, 0)
        component_layout.setSpacing(6)

        for key in ("adb", "scrcpy", "xcb"):
            component_layout.addWidget(self.create_dependency_row(key))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMaximumHeight(142)
        scroll.setWidget(content)
        dep_layout.addWidget(scroll)

        root.addWidget(dependencies)

        # Activity
        activity_header = QHBoxLayout()
        activity_title = QLabel("Activity")
        activity_title.setObjectName("SectionTitle")
        activity_header.addWidget(activity_title)
        activity_header.addStretch(1)

        activity_hint = QLabel("LIVE SYSTEM OUTPUT")
        activity_hint.setObjectName("SectionMeta")
        activity_header.addWidget(activity_hint)
        root.addLayout(activity_header)

        self.log = QTextEdit()
        self.log.setObjectName("ActivityLog")
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.setPlaceholderText("Waiting for setup activity...")
        self.log.setMinimumHeight(68)
        self.log.setFont(QFont("DejaVu Sans Mono", 9))
        root.addWidget(self.log, 1)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.retry_button = QPushButton("↻  Check again")
        self.retry_button.setObjectName("Quiet")
        self.retry_button.clicked.connect(self.run_check)
        footer.addWidget(self.retry_button)

        footer.addStretch(1)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_setup)

        self.continue_button = QPushButton("Start PhoneView")
        self.continue_button.setObjectName("Primary")
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setEnabled(False)

        footer.addWidget(self.cancel_button)
        footer.addWidget(self.continue_button)
        root.addLayout(footer)



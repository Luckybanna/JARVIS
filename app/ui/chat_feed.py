"""
Conversation Feed and Speech Bubble Widget for JARVIS HUD.
Renders clean right-aligned user speech bubbles and left-aligned JARVIS response cards.
"""

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatFeedWidget(QScrollArea):
    """
    Scrollable conversation history feed with styled message bubbles.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: transparent; border: none;")

        self.container = QWidget()
        self.container.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)
        self.layout.addStretch()

        self.setWidget(self.container)

    def add_user_message(self, text: str) -> None:
        """Appends a right-aligned user chat bubble."""
        row = QHBoxLayout()
        row.addStretch()

        bubble = QWidget()
        bubble.setStyleSheet("""
            background-color: #1f3a5f;
            border: 1px solid #2d5a88;
            border-radius: 12px;
            padding: 8px 12px;
        """)
        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(10, 8, 10, 8)
        b_layout.setSpacing(4)

        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet("color: #f0f6fc; font-size: 13px; background: transparent; border: none;")
        b_layout.addWidget(msg_lbl)

        time_str = datetime.now().strftime("%I:%M %p")
        time_lbl = QLabel(time_str)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_lbl.setStyleSheet("color: #8b949e; font-size: 10px; background: transparent; border: none;")
        b_layout.addWidget(time_lbl)

        row.addWidget(bubble)
        # Insert before bottom stretch
        self.layout.insertLayout(self.layout.count() - 1, row)
        self._scroll_to_bottom()

    def add_jarvis_message(self, text: str, model_tag: str = "") -> None:
        """Appends a left-aligned JARVIS response card."""
        row = QHBoxLayout()

        bubble = QWidget()
        bubble.setStyleSheet("""
            background-color: #161b22;
            border: 1px solid #30363d;
            border-left: 4px solid #00d2ff;
            border-radius: 12px;
            padding: 8px 12px;
        """)
        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(12, 8, 12, 8)
        b_layout.setSpacing(4)

        header_layout = QHBoxLayout()
        sender_lbl = QLabel("J.A.R.V.I.S.")
        sender_lbl.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 11px; background: transparent; border: none;")
        header_layout.addWidget(sender_lbl)

        if model_tag:
            tag_lbl = QLabel(f"[{model_tag}]")
            tag_lbl.setStyleSheet("color: #58a6ff; font-size: 10px; background: transparent; border: none;")
            header_layout.addWidget(tag_lbl)

        header_layout.addStretch()
        time_str = datetime.now().strftime("%I:%M %p")
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #8b949e; font-size: 10px; background: transparent; border: none;")
        header_layout.addWidget(time_lbl)
        b_layout.addLayout(header_layout)

        msg_lbl = QLabel(text)
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_lbl.setStyleSheet("color: #c9d1d9; font-size: 13px; line-height: 1.4; background: transparent; border: none;")
        b_layout.addWidget(msg_lbl)

        row.addWidget(bubble)
        row.addStretch()

        self.layout.insertLayout(self.layout.count() - 1, row)
        self._scroll_to_bottom()

    def clear_feed(self) -> None:
        """Clears all message bubbles from the feed."""
        while self.layout.count() > 1:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # delete child items
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def _scroll_to_bottom(self) -> None:
        # Schedule vertical scroll update after layout recalculation
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))

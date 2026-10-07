"""
QSS Stylesheets and Visual Constants for JARVIS Desktop HUD.
Sci-Fi Dark Theme with high-contrast glowing accents and clean typography.
"""

HUD_STYLESHEET = """
QMainWindow {
    background-color: #0b0f19;
}

QWidget {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    color: #c9d1d9;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    border: none;
    background: #0d1117;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #21262d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #30363d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QLineEdit {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 14px;
    color: #f0f6fc;
    font-size: 14px;
}

QLineEdit:focus {
    border: 1px solid #58a6ff;
    background-color: #0d1117;
}

QPushButton {
    background-color: #161b22;
    color: #f0f6fc;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #21262d;
    border-color: #58a6ff;
    color: #58a6ff;
}

QPushButton:pressed {
    background-color: #1f6feb;
    color: #ffffff;
}

QPushButton#mic_btn {
    border-radius: 20px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
    font-size: 16px;
    background-color: #161b22;
    border: 1px solid #30363d;
}

QPushButton#mic_btn:hover {
    border-color: #00d2ff;
    color: #00d2ff;
}

QPushButton#mic_btn[listening="true"] {
    background-color: #1f6feb;
    border: 1px solid #58a6ff;
    color: #ffffff;
}

QProgressBar {
    border: 1px solid #21262d;
    border-radius: 4px;
    background-color: #161b22;
    text-align: center;
    color: #8b949e;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #00d2ff;
    border-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #21262d;
    background-color: #0d1117;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #161b22;
    color: #8b949e;
    padding: 6px 14px;
    border: 1px solid #21262d;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 12px;
}

QTabBar::tab:selected {
    background-color: #0d1117;
    color: #58a6ff;
    border-color: #58a6ff;
    border-bottom: 1px solid #0d1117;
}

QGroupBox {
    border: 1px solid #21262d;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: bold;
    color: #58a6ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #0b0f19;
}
"""

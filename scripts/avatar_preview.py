"""
Interactive Avatar Visual Preview Harness for JARVIS.
Launches a PyQt6 window to visually inspect and test all 10 avatar states,
counter-rotating HUD rings, glowing core, and audio reactivity.
"""

import math
from pathlib import Path
import sys
import time

# Ensure root directory is on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.avatar.controller import AvatarController, get_avatar_controller
from app.avatar.renderer import AvatarRendererWidget
from app.avatar.state import AvatarState, AvatarTheme


class AvatarPreviewWindow(QMainWindow):
    """Interactive preview window for testing avatar visual dynamics."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS - Arc-Reactor Avatar Diagnostic")
        self.resize(800, 680)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f19;
            }
            QLabel {
                color: #c9d1d9;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                border: 1px solid #21262d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                color: #58a6ff;
                font-weight: bold;
            }
            QPushButton {
                background-color: #161b22;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #21262d;
                border-color: #58a6ff;
            }
            QPushButton:pressed {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #21262d;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #58a6ff;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f0f6fc;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
        """)

        self.controller = get_avatar_controller()

        # Speech simulation timer
        self._speech_sim_timer = QTimer(self)
        self._speech_sim_timer.setInterval(20)
        self._speech_sim_timer.timeout.connect(self._on_speech_sim_tick)
        self._sim_start_time: float = 0.0

        self._init_ui()
        self._update_info_panel(self.controller.current_state)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title header
        title_label = QLabel("J.A.R.V.I.S. Core Avatar Visualizer")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #58a6ff; letter-spacing: 2px;")
        main_layout.addWidget(title_label)

        # Avatar Center Widget
        self.avatar_widget = AvatarRendererWidget(controller=self.controller)
        main_layout.addWidget(self.avatar_widget, stretch=1)

        # Info Status Panel
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("""
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
        """)
        main_layout.addWidget(self.info_label)

        # Controls Container
        controls_group = QGroupBox("State & Reactivity Controls")
        controls_layout = QVBoxLayout(controls_group)

        # State buttons grid (2 rows x 5 columns)
        buttons_grid = QGridLayout()
        buttons_grid.setSpacing(8)

        states = list(AvatarState)
        for idx, state in enumerate(states):
            row = idx // 5
            col = idx % 5
            btn = QPushButton(state.value.upper())
            cfg = AvatarTheme.get_config(state)
            r, g, b = cfg.primary_color
            btn.setStyleSheet(f"""
                QPushButton {{
                    border-left: 4px solid rgb({r}, {g}, {b});
                }}
            """)
            btn.clicked.connect(lambda checked, s=state: self._select_state(s))
            buttons_grid.addWidget(btn, row, col)

        controls_layout.addLayout(buttons_grid)

        # Audio Reactivity Slider Row
        slider_layout = QHBoxLayout()
        slider_label = QLabel("Audio Reactivity (RMS):")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.slider_val_label = QLabel("0%")
        self.slider_val_label.setFixedWidth(40)

        self.sim_speech_btn = QPushButton("Simulate Speech Waveform")
        self.sim_speech_btn.clicked.connect(self._toggle_speech_simulation)

        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.slider_val_label)
        slider_layout.addWidget(self.sim_speech_btn)

        controls_layout.addLayout(slider_layout)
        main_layout.addWidget(controls_group)

    def _select_state(self, state: AvatarState):
        self.controller.set_state(state)
        self._update_info_panel(state)

    def _on_slider_changed(self, value: int):
        normalized = value / 100.0
        self.slider_val_label.setText(f"{value}%")
        self.controller.set_audio_level(normalized)

    def _toggle_speech_simulation(self):
        if self._speech_sim_timer.isActive():
            self._speech_sim_timer.stop()
            self.sim_speech_btn.setText("Simulate Speech Waveform")
            self.slider.setValue(0)
            self.controller.set_state(AvatarState.IDLE)
        else:
            self._sim_start_time = time.time()
            self.controller.set_state(AvatarState.SPEAKING)
            self._update_info_panel(AvatarState.SPEAKING)
            self.sim_speech_btn.setText("Stop Simulation")
            self._speech_sim_timer.start()

    def _on_speech_sim_tick(self):
        elapsed = time.time() - self._sim_start_time
        if elapsed > 6.0:  # 6 seconds demo
            self._toggle_speech_simulation()
            return
        # Pulsing pseudo-speech waveform combining multiple frequencies
        wave = (
            math.sin(elapsed * 8.0) * 0.4
            + math.sin(elapsed * 17.0) * 0.3
            + math.sin(elapsed * 3.0) * 0.3
        )
        level = max(0.05, min(1.0, abs(wave)))
        self.slider.setValue(int(level * 100))

    def _update_info_panel(self, state: AvatarState):
        cfg = AvatarTheme.get_config(state)
        self.info_label.setText(
            f"State: {state.value.upper()} | "
            f"Primary RGB: {cfg.primary_color} | Glow RGB: {cfg.glow_color} | "
            f"Rot Speed: {cfg.rotation_speed} deg/f | Pulse Freq: {cfg.pulse_freq}x | "
            f"Base Scale: {cfg.base_scale}x | Info: {cfg.description}"
        )


def main():
    app = QApplication(sys.argv)
    window = AvatarPreviewWindow()
    window.show()
    print("[OK] Avatar visual preview launched successfully.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

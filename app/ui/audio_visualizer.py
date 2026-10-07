"""
Reactive Audio Equalizer / Spectrum Visualizer Widget for JARVIS HUD.
Visualizes real-time microphone RMS capture and speech synthesis output with glowing bars.
"""

import math
import random
from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class AudioVisualizerWidget(QWidget):
    """
    Renders a dynamic, glowing multi-bar audio visualizer spectrum.
    """

    def __init__(self, parent: Optional[QWidget] = None, num_bars: int = 24):
        super().__init__(parent)
        self.num_bars = num_bars
        self._level: float = 0.0
        self._bar_heights: List[float] = [0.0] * num_bars
        self._target_heights: List[float] = [0.0] * num_bars

        self.setFixedHeight(36)
        self.setMinimumWidth(200)

        # 40 FPS decay / animation timer
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def set_level(self, level: float) -> None:
        """Sets target audio amplitude (0.0 to 1.0)."""
        self._level = max(0.0, min(1.0, float(level)))
        # Generate pseudo-spectral profile across the bars
        for i in range(self.num_bars):
            mid = self.num_bars / 2.0
            dist_factor = 1.0 - (abs(i - mid) / mid) * 0.4
            noise = random.uniform(0.75, 1.25)
            self._target_heights[i] = min(1.0, self._level * dist_factor * noise)

    def _on_tick(self) -> None:
        # Smoothly interpolate bars toward target with decay
        for i in range(self.num_bars):
            target = self._target_heights[i]
            # Rapid rise, smooth decay
            if target > self._bar_heights[i]:
                self._bar_heights[i] += (target - self._bar_heights[i]) * 0.5
            else:
                self._bar_heights[i] += (target - self._bar_heights[i]) * 0.2

            # Decay target over time
            self._target_heights[i] *= 0.88

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        bar_spacing = 3.0
        total_spacing = bar_spacing * (self.num_bars - 1)
        bar_width = max(2.0, (w - total_spacing) / self.num_bars)

        max_bar_h = h * 0.85
        cy = h / 2.0

        for i in range(self.num_bars):
            x = i * (bar_width + bar_spacing)
            bar_pct = max(0.06, self._bar_heights[i])
            bar_h = max_bar_h * bar_pct

            # Gradient from deep cyan to neon blue
            grad = QLinearGradient(x, cy - bar_h / 2.0, x, cy + bar_h / 2.0)
            grad.setColorAt(0.0, QColor(0, 210, 255, 230))
            grad.setColorAt(0.5, QColor(88, 166, 255, 255))
            grad.setColorAt(1.0, QColor(0, 160, 220, 200))

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            rect = QRectF(x, cy - bar_h / 2.0, bar_width, bar_h)
            painter.drawRoundedRect(rect, 2.0, 2.0)

        painter.end()

    def closeEvent(self, event):
        if self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)

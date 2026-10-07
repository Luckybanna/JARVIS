"""
Avatar Arc-Reactor Geometric Renderer for JARVIS.
PyQt6 QWidget featuring concentric counter-rotating HUD rings, glowing radial gradients,
audio-reactive amplitude scaling, and smooth color/state interpolation.
"""

import math
import time
from typing import Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from app.avatar.controller import AvatarController, get_avatar_controller
from app.avatar.state import AvatarState, AvatarTheme, StateVisualConfig
from app.core.logger import get_logger

logger = get_logger("avatar.renderer")


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(
    c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
    )


class AvatarRendererWidget(QWidget):
    """
    60 FPS Arc-Reactor animated widget rendering JARVIS's visual persona.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        controller: Optional[AvatarController] = None,
        enable_timer: bool = True,
    ):
        super().__init__(parent)
        self.controller = controller or get_avatar_controller()

        # Canvas settings
        self.setMinimumSize(180, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        # Animation state
        self._current_state: AvatarState = self.controller.current_state
        self._target_config: StateVisualConfig = AvatarTheme.get_config(self._current_state)

        # Current interpolated visual values
        self._current_primary: Tuple[int, int, int] = self._target_config.primary_color
        self._current_glow: Tuple[int, int, int] = self._target_config.glow_color
        self._current_speed: float = self._target_config.rotation_speed
        self._current_pulse_freq: float = self._target_config.pulse_freq
        self._current_scale: float = self._target_config.base_scale

        # Dynamic animation angles and phases
        self._outer_angle: float = 0.0      # Clockwise rotation degrees
        self._middle_angle: float = 0.0     # Counter-clockwise rotation degrees
        self._pulse_phase: float = 0.0      # Sine wave phase
        self._audio_level: float = 0.0      # Audio reactivity (0.0 to 1.0)
        self._last_frame_time: float = time.perf_counter()

        # 60 FPS Render Timer
        self._timer: Optional[QTimer] = None
        if enable_timer:
            self._start_animation_timer()

    def _start_animation_timer(self) -> None:
        """Starts 60 FPS QTimer (16ms interval)."""
        try:
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._on_tick)
            self._timer.start()
        except Exception as e:
            logger.warning(f"Could not start avatar animation timer (possibly headless): {e}")

    def _on_tick(self) -> None:
        """Frame update callback."""
        now = time.perf_counter()
        dt = min(0.1, max(0.001, now - self._last_frame_time))
        self._last_frame_time = now

        # Sync state and audio level from controller
        if self.controller:
            if self.controller.current_state != self._current_state:
                self.set_state(self.controller.current_state)
            self._audio_level = self.controller.audio_level

        self.advance_frame(dt)
        self.update()

    def set_state(self, state: AvatarState) -> None:
        """Switches target avatar state and triggers visual interpolation."""
        self._current_state = state
        self._target_config = AvatarTheme.get_config(state)

    def set_audio_level(self, level: float) -> None:
        """Sets real-time audio amplitude for pulse scaling."""
        self._audio_level = max(0.0, min(1.0, float(level)))

    def advance_frame(self, dt: float = 0.016) -> None:
        """
        Advances animation math by dt seconds.
        Decoupled from paintEvent for deterministic testing.
        """
        # Smooth interpolation toward target visual config (blend factor ~ 6 * dt)
        blend = min(1.0, 6.0 * dt)
        self._current_primary = _lerp_color(self._current_primary, self._target_config.primary_color, blend)
        self._current_glow = _lerp_color(self._current_glow, self._target_config.glow_color, blend)
        self._current_speed = _lerp(self._current_speed, self._target_config.rotation_speed, blend)
        self._current_pulse_freq = _lerp(self._current_pulse_freq, self._target_config.pulse_freq, blend)
        self._current_scale = _lerp(self._current_scale, self._target_config.base_scale, blend)

        # Advance rotation angles (degrees)
        self._outer_angle = (self._outer_angle + self._current_speed * 60.0 * dt) % 360.0
        self._middle_angle = (self._middle_angle - self._current_speed * 45.0 * dt) % 360.0

        # Advance breathing / pulsing sine phase (radians)
        self._pulse_phase = (self._pulse_phase + self._current_pulse_freq * 3.5 * dt) % (2.0 * math.pi)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Renders the Arc-Reactor avatar."""
        painter = QPainter(self)
        self._draw_avatar(painter, self.width(), self.height())
        painter.end()

    def render_to_pixmap(self, width: int = 300, height: int = 300) -> QPixmap:
        """Renders the current avatar state onto an in-memory QPixmap."""
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self._draw_avatar(painter, width, height)
        painter.end()
        return pixmap

    def _draw_avatar(self, painter: QPainter, width: int, height: int) -> None:
        """Core rendering logic using QPainter vector paths and radial gradients."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cx = width / 2.0
        cy = height / 2.0
        base_radius = min(width, height) * 0.42

        # Compute dynamic scale (base scale + subtle pulse + audio reactivity)
        pulse = math.sin(self._pulse_phase) * 0.05
        audio_boost = self._audio_level * 0.22
        effective_scale = self._current_scale + pulse + audio_boost
        radius = base_radius * effective_scale

        pr, pg, pb = self._current_primary
        gr, gg, gb = self._current_glow

        primary_qcolor = QColor(pr, pg, pb)
        glow_qcolor = QColor(gr, gg, gb)

        # -------------------------------------------------------------
        # Layer 1: Ambient Outer Radial Glow
        # -------------------------------------------------------------
        outer_glow = QRadialGradient(QPointF(cx, cy), radius * 1.3)
        outer_glow.setColorAt(0.0, QColor(gr, gg, gb, int(60 + 80 * self._audio_level)))
        outer_glow.setColorAt(0.6, QColor(gr, gg, gb, 25))
        outer_glow.setColorAt(1.0, QColor(gr, gg, gb, 0))
        painter.setBrush(QBrush(outer_glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 1.3, radius * 1.3)

        # -------------------------------------------------------------
        # Layer 2: Outer Segmented Ring & Tick Marks (Clockwise)
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._outer_angle)

        outer_pen = QPen(QColor(pr, pg, pb, 160), 2.2)
        outer_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(outer_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        r_outer = radius * 0.95
        painter.drawEllipse(QPointF(0, 0), r_outer, r_outer)

        # Outer tick notches (24 notches around circumference)
        num_ticks = 24
        tick_pen_accent = QPen(primary_qcolor, 2.5)
        tick_pen_subtle = QPen(QColor(pr, pg, pb, 90), 1.2)

        for i in range(num_ticks):
            is_accent = (i % 6 == 0)
            painter.setPen(tick_pen_accent if is_accent else tick_pen_subtle)
            tick_len = 10 if is_accent else 5
            painter.drawLine(0, int(r_outer - tick_len), 0, int(r_outer + tick_len))
            painter.rotate(360.0 / num_ticks)

        painter.restore()

        # -------------------------------------------------------------
        # Layer 3: Middle Arc Brackets (Counter-Clockwise)
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._middle_angle)

        r_mid = radius * 0.72
        mid_pen = QPen(QColor(pr, pg, pb, 210), 3.5)
        mid_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(mid_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw 4 segmented arcs with gaps
        rect_mid = QRectF(-r_mid, -r_mid, r_mid * 2, r_mid * 2)
        for i in range(4):
            start_deg = i * 90 + 12
            span_deg = 66
            painter.drawArc(rect_mid, int(start_deg * 16), int(span_deg * 16))

        painter.restore()

        # -------------------------------------------------------------
        # Layer 4: Inner Track & Energy Nodes
        # -------------------------------------------------------------
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._outer_angle * 0.5)

        r_inner = radius * 0.48
        inner_pen = QPen(QColor(gr, gg, gb, 140), 1.5)
        painter.setPen(inner_pen)
        painter.drawEllipse(QPointF(0, 0), r_inner, r_inner)

        # 8 small energy nodes on the inner ring
        node_brush = QBrush(primary_qcolor)
        painter.setBrush(node_brush)
        painter.setPen(Qt.PenStyle.NoPen)
        for _ in range(8):
            painter.drawEllipse(QPointF(0, -r_inner), 2.8, 2.8)
            painter.rotate(45.0)

        painter.restore()

        # -------------------------------------------------------------
        # Layer 5: Glowing Core (Arc-Reactor Center)
        # -------------------------------------------------------------
        r_core = radius * 0.32 * (1.0 + self._audio_level * 0.3)
        core_grad = QRadialGradient(QPointF(cx, cy), r_core)
        # Intense luminous center
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 240))
        core_grad.setColorAt(0.4, QColor(pr, pg, pb, 220))
        core_grad.setColorAt(0.8, QColor(gr, gg, gb, 160))
        core_grad.setColorAt(1.0, QColor(gr, gg, gb, 0))

        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r_core, r_core)

        # Center highlight dot
        highlight_color = QColor(255, 255, 255, 230)
        painter.setBrush(QBrush(highlight_color))
        painter.drawEllipse(QPointF(cx, cy), r_core * 0.22, r_core * 0.22)

    def closeEvent(self, event) -> None:
        """Ensures animation timer stops upon window close."""
        if self._timer and self._timer.isActive():
            self._timer.stop()
        super().closeEvent(event)

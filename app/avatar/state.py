"""
Avatar Visual States and Theme Definitions for JARVIS.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple


class AvatarState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY = "happy"
    CONCERNED = "concerned"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    SLEEPING = "sleeping"


@dataclass
class StateVisualConfig:
    """Color, rotation, and animation parameters for a specific avatar state."""
    primary_color: Tuple[int, int, int]   # RGB
    glow_color: Tuple[int, int, int]      # RGB
    rotation_speed: float                 # Degrees per frame
    pulse_freq: float                     # Pulse speed factor
    base_scale: float                     # Relative size scale (0.8 - 1.2)
    description: str


class AvatarTheme:
    """Maps avatar states to visual styles."""

    PALETTES: Dict[AvatarState, StateVisualConfig] = {
        AvatarState.IDLE: StateVisualConfig(
            primary_color=(0, 210, 255),       # Classic Cyan
            glow_color=(0, 160, 220),
            rotation_speed=0.6,
            pulse_freq=1.0,
            base_scale=1.0,
            description="Calm, observant resting state",
        ),
        AvatarState.LISTENING: StateVisualConfig(
            primary_color=(30, 144, 255),      # Neon Blue
            glow_color=(0, 100, 255),
            rotation_speed=1.2,
            pulse_freq=1.8,
            base_scale=1.08,
            description="Microphone active, listening to user speech",
        ),
        AvatarState.THINKING: StateVisualConfig(
            primary_color=(140, 90, 255),      # Violet-Blue
            glow_color=(100, 50, 240),
            rotation_speed=3.2,
            pulse_freq=2.5,
            base_scale=1.04,
            description="AI reasoning and LLM generation active",
        ),
        AvatarState.SPEAKING: StateVisualConfig(
            primary_color=(0, 255, 180),       # Emerald / Bright Teal
            glow_color=(0, 200, 130),
            rotation_speed=1.5,
            pulse_freq=3.0,
            base_scale=1.12,
            description="Synthesizing and delivering voice output",
        ),
        AvatarState.HAPPY: StateVisualConfig(
            primary_color=(255, 215, 0),       # Warm Gold
            glow_color=(230, 170, 0),
            rotation_speed=1.2,
            pulse_freq=1.6,
            base_scale=1.06,
            description="Pleased, encouraged cognitive posture",
        ),
        AvatarState.CONCERNED: StateVisualConfig(
            primary_color=(255, 140, 0),       # Amber / Orange
            glow_color=(210, 100, 0),
            rotation_speed=0.8,
            pulse_freq=1.4,
            base_scale=0.98,
            description="High empathy, recognizing user difficulty",
        ),
        AvatarState.SAD: StateVisualConfig(
            primary_color=(90, 120, 180),      # Steel / Muted Blue
            glow_color=(60, 80, 140),
            rotation_speed=0.3,
            pulse_freq=0.7,
            base_scale=0.92,
            description="Subdued, sympathetic posture",
        ),
        AvatarState.ANGRY: StateVisualConfig(
            primary_color=(255, 50, 60),       # Crimson Red
            glow_color=(200, 20, 30),
            rotation_speed=2.5,
            pulse_freq=3.5,
            base_scale=1.05,
            description="Sharp, alert, boundary violation",
        ),
        AvatarState.SURPRISED: StateVisualConfig(
            primary_color=(240, 250, 255),     # Starlight White
            glow_color=(180, 220, 255),
            rotation_speed=2.0,
            pulse_freq=4.0,
            base_scale=1.20,
            description="High unexpectedness or revelation",
        ),
        AvatarState.SLEEPING: StateVisualConfig(
            primary_color=(40, 65, 95),        # Deep Slate Blue
            glow_color=(25, 40, 65),
            rotation_speed=0.15,
            pulse_freq=0.4,
            base_scale=0.85,
            description="Dormant low-power background mode",
        ),
    }

    @classmethod
    def get_config(cls, state: AvatarState) -> StateVisualConfig:
        return cls.PALETTES.get(state, cls.PALETTES[AvatarState.IDLE])

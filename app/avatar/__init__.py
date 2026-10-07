"""
Animated Avatar Subsystem for JARVIS.
Decoupled visual presentation layer with reactive geometric arc-reactor rendering and state control.
"""

from app.avatar.state import AvatarState, AvatarTheme
from app.avatar.controller import AvatarController, get_avatar_controller
from app.avatar.renderer import AvatarRendererWidget

__all__ = [
    "AvatarState",
    "AvatarTheme",
    "AvatarController",
    "get_avatar_controller",
    "AvatarRendererWidget",
]

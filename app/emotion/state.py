"""
Simulated Internal Emotional State for JARVIS.
Represents an explicit, controllable 9-dimensional state vector (0-100 scales).
NOTE: JARVIS has no biological feelings; this is a simulated cognitive posture.
"""

from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class EmotionState:
    """Internal simulated emotion vector of JARVIS (values clamped from 0 to 100)."""

    happiness: int = 70
    sadness: int = 10
    anger: int = 0
    fear: int = 0
    curiosity: int = 80
    concern: int = 20
    confidence: int = 85
    energy: int = 70
    trust: int = 60

    # Baseline anchor values for gradual natural decay
    BASELINE = {
        "happiness": 70,
        "sadness": 10,
        "anger": 0,
        "fear": 0,
        "curiosity": 80,
        "concern": 20,
        "confidence": 85,
        "energy": 70,
        "trust": 60,
    }

    def __post_init__(self):
        self._clamp_all()

    def _clamp(self, val: int) -> int:
        return max(0, min(100, int(val)))

    def _clamp_all(self) -> None:
        self.happiness = self._clamp(self.happiness)
        self.sadness = self._clamp(self.sadness)
        self.anger = self._clamp(self.anger)
        self.fear = self._clamp(self.fear)
        self.curiosity = self._clamp(self.curiosity)
        self.concern = self._clamp(self.concern)
        self.confidence = self._clamp(self.confidence)
        self.energy = self._clamp(self.energy)
        self.trust = self._clamp(self.trust)

    def to_dict(self) -> Dict[str, int]:
        """Returns the emotional state vector as a clean dictionary."""
        return asdict(self)

    def dominant_emotion(self) -> str:
        """Returns the non-baseline emotion currently showing greatest elevation."""
        elevations = {
            "curiosity": self.curiosity - self.BASELINE["curiosity"],
            "concern": self.concern - self.BASELINE["concern"],
            "happiness": self.happiness - self.BASELINE["happiness"],
            "confidence": self.confidence - self.BASELINE["confidence"],
            "energy": self.energy - self.BASELINE["energy"],
            "sadness": self.sadness - self.BASELINE["sadness"],
            "anger": self.anger - self.BASELINE["anger"],
            "fear": self.fear - self.BASELINE["fear"],
        }
        top = max(elevations.items(), key=lambda x: x[1])
        if top[1] > 5:
            return top[0]
        return "calm"

    def decay_toward_baseline(self, rate: float = 0.15) -> None:
        """Gradually pulls emotional state back toward default resting baseline."""
        for field_name, base_val in self.BASELINE.items():
            curr_val = getattr(self, field_name)
            diff = base_val - curr_val
            if abs(diff) > 0:
                step = int(round(diff * rate))
                if step == 0 and diff != 0:
                    step = 1 if diff > 0 else -1
                setattr(self, field_name, self._clamp(curr_val + step))

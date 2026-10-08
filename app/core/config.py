"""
Configuration management for JARVIS.
Loads environment variables (.env) and JSON configuration files with type validation.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure essential runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env if present
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    """Central configuration class for JARVIS assistant."""

    def __init__(self, config_file: Optional[Path] = None):
        self.project_root: Path = PROJECT_ROOT
        self.data_dir: Path = DATA_DIR
        self.logs_dir: Path = LOGS_DIR

        # Load default json config
        self._config_file = config_file or (CONFIG_DIR / "default_config.json")
        self._raw_config: Dict[str, Any] = {}
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    self._raw_config = json.load(f)
            except Exception as e:
                self._raw_config = {}

        # App / Environment
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        # AI Provider configuration
        self.ai_provider: str = os.getenv(
            "AI_PROVIDER",
            self._raw_config.get("ai", {}).get("default_provider", "gemini"),
        ).lower().strip()

        # Google Gemini
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

        # OpenAI
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

        # Local Provider
        self.local_api_base_url: str = os.getenv(
            "LOCAL_API_BASE_URL", "http://localhost:11434/v1"
        ).strip()
        self.local_model: str = os.getenv("LOCAL_MODEL", "llama3.2").strip()

        # Inference params
        ai_cfg = self._raw_config.get("ai", {})
        self.ai_timeout: float = float(ai_cfg.get("timeout_seconds", 30.0))
        self.ai_max_retries: int = int(ai_cfg.get("max_retries", 2))
        self.ai_temperature: float = float(ai_cfg.get("temperature", 0.7))
        self.ai_max_tokens: int = int(ai_cfg.get("max_tokens", 1024))

        # Assistant metadata
        ast_cfg = self._raw_config.get("assistant", {})
        self.assistant_name: str = ast_cfg.get("name", "JARVIS")
        self.primary_language: str = ast_cfg.get("primary_language", "hinglish")
        self.supported_languages: List[str] = ast_cfg.get(
            "supported_languages", ["en", "hi", "hinglish"]
        )

        # Voice Settings
        v_cfg = self._raw_config.get("voice", {})
        self.tts_provider: str = os.getenv("TTS_PROVIDER", v_cfg.get("tts_provider", "edge_tts"))
        self.edge_tts_voice_hindi: str = os.getenv(
            "EDGE_TTS_VOICE_HINDI", v_cfg.get("edge_tts_voice_hindi", "hi-IN-SwaraNeural")
        )
        self.edge_tts_voice_english: str = os.getenv(
            "EDGE_TTS_VOICE_ENGLISH", v_cfg.get("edge_tts_voice_english", "hi-IN-SwaraNeural")
        )
        self.sapi_fallback_enabled: bool = False
        self.speech_rate: str = os.getenv("SPEECH_RATE", v_cfg.get("speech_rate", "+0%"))
        self.speech_volume: str = os.getenv("SPEECH_VOLUME", v_cfg.get("speech_volume", "+0%"))
        self.mic_energy_threshold: int = int(v_cfg.get("mic_energy_threshold", 300))
        self.mic_silence_timeout_seconds: float = float(
            v_cfg.get("mic_silence_timeout_seconds", 1.5)
        )

        # Proactive conversation settings
        p_cfg = self._raw_config.get("proactive", {})
        self.proactive_enabled: bool = bool(p_cfg.get("enabled", True))
        self.min_proactive_interval_min: int = int(
            p_cfg.get("minimum_proactive_interval_minutes", 45)
        )
        self.max_proactive_per_hour: int = int(
            p_cfg.get("maximum_proactive_messages_per_hour", 2)
        )
        self.break_suggestion_work_min: int = int(
            p_cfg.get("continuous_work_break_suggestion_minutes", 90)
        )
        self.quiet_hours_enabled: bool = bool(p_cfg.get("quiet_hours_enabled", True))
        self.quiet_hours_start: str = p_cfg.get("quiet_hours_start", "23:00")
        self.quiet_hours_end: str = p_cfg.get("quiet_hours_end", "07:00")
        self.do_not_disturb: bool = bool(p_cfg.get("do_not_disturb", False))
        self.meeting_mode: bool = bool(p_cfg.get("meeting_mode", False))

        # Safe PC Tools settings
        t_cfg = self._raw_config.get("tools", {})
        self.confirm_dangerous_actions: bool = bool(
            t_cfg.get("confirm_dangerous_actions", True)
        )
        self.allowed_applications: List[str] = t_cfg.get(
            "allowed_applications",
            ["notepad.exe", "calc.exe", "explorer.exe", "chrome.exe", "msedge.exe"],
        )

    def mask_key(self, key: str) -> str:
        """Returns masked API key for safe debugging/telemetry display."""
        if not key:
            return "[NOT SET]"
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def get_active_api_key(self) -> str:
        """Returns the API key for the currently active AI provider."""
        if self.ai_provider == "gemini":
            return self.gemini_api_key
        elif self.ai_provider == "openai":
            return self.openai_api_key
        return ""

    def validate_provider_config(self, provider_name: Optional[str] = None) -> tuple[bool, str]:
        """Validates whether the requested or active provider is properly configured."""
        prov = (provider_name or self.ai_provider).lower()
        if prov == "gemini":
            if not self.gemini_api_key:
                return False, "GEMINI_API_KEY is not set in environment or .env file"
            return True, "Configured"
        elif prov == "openai":
            if not self.openai_api_key:
                return False, "OPENAI_API_KEY is not set in environment or .env file"
            return True, "Configured"
        elif prov == "local":
            if not self.local_api_base_url:
                return False, "LOCAL_API_BASE_URL is not configured"
            return True, "Configured"
        return False, f"Unknown AI provider: '{prov}'. Supported: 'gemini', 'openai', 'local'"

    def __repr__(self) -> str:
        return (
            f"<Settings provider={self.ai_provider} "
            f"gemini_key={self.mask_key(self.gemini_api_key)} "
            f"openai_key={self.mask_key(self.openai_api_key)} "
            f"debug={self.debug}>"
        )


_settings_instance: Optional[Settings] = None


def get_settings(reload: bool = False, config_file: Optional[Path] = None) -> Settings:
    """Singleton getter for application settings."""
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = Settings(config_file=config_file)
    return _settings_instance

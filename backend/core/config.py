"""Centralised runtime configuration for the HELIX backend.

Every tunable that used to be a module-level constant scattered across the
services now lives here, so operators can change network capacity, LLM model
or persistence location with environment variables instead of code edits.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    return int(_get_float(name, float(default)))


def _get_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Application settings resolved from the environment.

    Plain attributes (rather than pydantic-settings) keep the dependency
    surface small; the backend already requires ``python-dotenv`` and nothing
    here needs coercion beyond the small helpers above.
    """

    def __init__(self) -> None:
        # --- Identity -----------------------------------------------------
        self.app_name: str = os.getenv("HELIX_APP_NAME", "HELIX")
        self.version: str = "2.0.0"
        self.environment: str = os.getenv("HELIX_ENV", "development")

        # --- HTTP ---------------------------------------------------------
        self.host: str = os.getenv("HELIX_HOST", "0.0.0.0")
        self.port: int = _get_int("HELIX_PORT", 8000)
        self.cors_origins: list[str] = _get_list("HELIX_CORS_ORIGINS", ["*"])
        # Write requests per client per minute; 0 disables the limiter.
        self.rate_limit_per_minute: int = _get_int("HELIX_RATE_LIMIT_PER_MINUTE", 60)

        # --- Radio / transport capacity ------------------------------------
        self.total_bandwidth_mbps: float = _get_float("HELIX_TOTAL_BANDWIDTH_MBPS", 1000.0)
        self.max_devices_shared_isolation: int = _get_int("HELIX_MAX_SHARED_DEVICES", 10_000)

        # --- LLM intent parsing --------------------------------------------
        self.groq_api_key: str | None = os.getenv("GROQ_API_KEY") or None
        self.groq_model: str = os.getenv("HELIX_GROQ_MODEL", "llama-3.3-70b-versatile")
        self.llm_temperature: float = _get_float("HELIX_LLM_TEMPERATURE", 0.2)
        self.llm_max_tokens: int = _get_int("HELIX_LLM_MAX_TOKENS", 1024)
        self.llm_timeout_seconds: float = _get_float("HELIX_LLM_TIMEOUT_SECONDS", 30.0)
        # When true the deterministic parser is always used, even if a key exists.
        self.force_rule_based_parser: bool = _get_bool("HELIX_FORCE_RULE_PARSER", False)

        # --- Persistence ----------------------------------------------------
        self.persistence_enabled: bool = _get_bool("HELIX_PERSISTENCE_ENABLED", True)
        self.database_path: Path = Path(
            os.getenv("HELIX_DATABASE_PATH", str(BASE_DIR / "data" / "helix.db"))
        )
        self.seed_demo_slices: bool = _get_bool("HELIX_SEED_DEMO_SLICES", True)

        # --- Telemetry -------------------------------------------------------
        self.telemetry_enabled: bool = _get_bool("HELIX_TELEMETRY_ENABLED", True)
        self.telemetry_interval_seconds: float = _get_float("HELIX_TELEMETRY_INTERVAL", 2.0)
        self.telemetry_history_size: int = _get_int("HELIX_TELEMETRY_HISTORY", 120)

        # --- SDN controller simulation ------------------------------------------
        # Scales every simulated deployment step; set to 0 for instant deploys.
        self.sdn_step_scale: float = _get_float("HELIX_SDN_STEP_SCALE", 1.0)
        self.sdn_failure_rate: float = _get_float("HELIX_SDN_FAILURE_RATE", 0.0)
        self.sdn_controller_name: str = os.getenv("HELIX_SDN_CONTROLLER", "Ryu SDN Controller")

        # --- Logging ---------------------------------------------------------
        self.log_level: str = os.getenv("HELIX_LOG_LEVEL", "INFO").upper()
        self.log_json: bool = _get_bool("HELIX_LOG_JSON", False)

    @property
    def llm_available(self) -> bool:
        """True when an LLM-backed parser can actually be constructed."""
        return bool(self.groq_api_key) and not self.force_rule_based_parser

    def as_dict(self) -> dict:
        """Non-secret view of the configuration, safe to expose over the API."""
        return {
            "app_name": self.app_name,
            "version": self.version,
            "environment": self.environment,
            "total_bandwidth_mbps": self.total_bandwidth_mbps,
            "groq_model": self.groq_model,
            "llm_available": self.llm_available,
            "persistence_enabled": self.persistence_enabled,
            "telemetry_enabled": self.telemetry_enabled,
            "telemetry_interval_seconds": self.telemetry_interval_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()

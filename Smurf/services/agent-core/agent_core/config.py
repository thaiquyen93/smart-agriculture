"""Config contract for agent-core.

`services/agent-core/.env.example` is the source of truth for every variable
name and default here — keep them in sync when either file changes.

Rule 4 (services/agent-core/CLAUDE.md): "Provider switch is config, not code."
`Settings.llm_profile_config()` is the ONLY place that branches on
LLM_PROFILE; everything downstream (agent_core.llm.*) only ever sees the
resolved `LLMProfileConfig`, never a raw env var or an `if profile == ...`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw not in (None, "") else default


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw not in (None, "") else default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class LLMProfileConfig:
    """The only shape `agent_core.llm.*` is allowed to depend on. No field
    here names a provider ("gemini", "local") in a way agent code branches
    on — `profile` is carried through only for logging / AgentEvent.llm_call.
    """

    profile: str
    base_url: str
    model: str
    api_key: str
    max_dispatch_rounds: int
    use_native_tool_calling: bool
    timeout_sec: float
    temperature_decision: float
    temperature_narrative: float


@dataclass(frozen=True)
class Settings:
    # --- Kafka / Redpanda (shared with the other services, do not rename) ---
    kafka_bootstrap_servers: str
    topic_raw: str
    topic_p: str
    topic_h: str

    # --- Topics agent-core produces ---
    topic_agent_events: str
    topic_plans: str
    topic_tasks: str
    topic_notifications: str
    topic_verifications: str

    # --- LLM provider selection ---
    llm_profile: str

    local_llm_base_url: str
    local_llm_model: str
    local_llm_api_key: str
    local_max_dispatch_rounds: int
    local_use_native_tool_calling: bool

    gemini_llm_base_url: str
    gemini_llm_model: str
    gemini_llm_api_key: str
    gemini_max_dispatch_rounds: int
    gemini_use_native_tool_calling: bool

    llm_temperature_decision: float
    llm_temperature_narrative: float
    llm_timeout_sec: float
    agent_max_workers: int

    # --- Freshness thresholds (docs/agent-core/01-architecture.md §5.2) ---
    freshness_fresh_sec: int
    freshness_stale_sec: int

    # --- Policy Gate — deterministic, never LLM-decided (02-agents-and-tools.md §B.7) ---
    policy_min_tank_level_pct: float
    policy_approval_threshold_liters: float
    policy_max_volume_liters: float
    policy_max_duration_minutes: int

    # --- ML model registry (05-ml-interfaces.md) ---
    model_soil_forecaster: str
    model_water_demand: str
    model_pump_health: str
    model_anomaly: str

    agent_core_port: int

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        # Default to services/agent-core/.env — harmless no-op if it doesn't
        # exist (e.g. in Docker, where docker-compose supplies env vars
        # directly and no .env file is copied into the image).
        default_env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_file or default_env_path)

        return cls(
            kafka_bootstrap_servers=_env_str("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            topic_raw=_env_str("TOPIC_RAW", "topic_raw"),
            topic_p=_env_str("TOPIC_P", "topic_p"),
            topic_h=_env_str("TOPIC_H", "topic_h"),
            topic_agent_events=_env_str("TOPIC_AGENT_EVENTS", "topic_agent_events"),
            topic_plans=_env_str("TOPIC_PLANS", "topic_plans"),
            topic_tasks=_env_str("TOPIC_TASKS", "topic_tasks"),
            topic_notifications=_env_str("TOPIC_NOTIFICATIONS", "topic_notifications"),
            topic_verifications=_env_str("TOPIC_VERIFICATIONS", "topic_verifications"),
            llm_profile=_env_str("LLM_PROFILE", "local"),
            local_llm_base_url=_env_str("LOCAL_LLM_BASE_URL", "http://localhost:1234/v1"),
            local_llm_model=_env_str("LOCAL_LLM_MODEL", "qwen2.5-3b-instruct"),
            local_llm_api_key=_env_str("LOCAL_LLM_API_KEY", "lm-studio"),
            local_max_dispatch_rounds=_env_int("LOCAL_MAX_DISPATCH_ROUNDS", 2),
            local_use_native_tool_calling=_env_bool("LOCAL_USE_NATIVE_TOOL_CALLING", False),
            gemini_llm_base_url=_env_str(
                "GEMINI_LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
            ),
            gemini_llm_model=_env_str("GEMINI_LLM_MODEL", "gemini-2.5-flash"),
            gemini_llm_api_key=_env_str("GEMINI_LLM_API_KEY", ""),
            gemini_max_dispatch_rounds=_env_int("GEMINI_MAX_DISPATCH_ROUNDS", 4),
            gemini_use_native_tool_calling=_env_bool("GEMINI_USE_NATIVE_TOOL_CALLING", True),
            llm_temperature_decision=_env_float("LLM_TEMPERATURE_DECISION", 0.1),
            llm_temperature_narrative=_env_float("LLM_TEMPERATURE_NARRATIVE", 0.6),
            llm_timeout_sec=_env_float("LLM_TIMEOUT_SEC", 60.0),
            agent_max_workers=_env_int("AGENT_MAX_WORKERS", 4),
            freshness_fresh_sec=_env_int("FRESHNESS_FRESH_SEC", 60),
            freshness_stale_sec=_env_int("FRESHNESS_STALE_SEC", 600),
            policy_min_tank_level_pct=_env_float("POLICY_MIN_TANK_LEVEL_PCT", 20.0),
            policy_approval_threshold_liters=_env_float("POLICY_APPROVAL_THRESHOLD_LITERS", 500.0),
            policy_max_volume_liters=_env_float("POLICY_MAX_VOLUME_LITERS", 2000.0),
            policy_max_duration_minutes=_env_int("POLICY_MAX_DURATION_MINUTES", 120),
            model_soil_forecaster=_env_str("MODEL_SOIL_FORECASTER", "baseline"),
            model_water_demand=_env_str("MODEL_WATER_DEMAND", "baseline"),
            model_pump_health=_env_str("MODEL_PUMP_HEALTH", "baseline"),
            model_anomaly=_env_str("MODEL_ANOMALY", "baseline"),
            agent_core_port=_env_int("AGENT_CORE_PORT", 8100),
        )

    def llm_profile_config(self) -> LLMProfileConfig:
        """The single branch point for LLM_PROFILE. Nothing outside this
        method should ever compare `llm_profile` to a string literal."""
        if self.llm_profile == "gemini":
            return LLMProfileConfig(
                profile="gemini",
                base_url=self.gemini_llm_base_url,
                model=self.gemini_llm_model,
                api_key=self.gemini_llm_api_key,
                max_dispatch_rounds=self.gemini_max_dispatch_rounds,
                use_native_tool_calling=self.gemini_use_native_tool_calling,
                timeout_sec=self.llm_timeout_sec,
                temperature_decision=self.llm_temperature_decision,
                temperature_narrative=self.llm_temperature_narrative,
            )
        if self.llm_profile != "local":
            raise ValueError(f"Unknown LLM_PROFILE={self.llm_profile!r} — expected 'local' or 'gemini'")
        return LLMProfileConfig(
            profile="local",
            base_url=self.local_llm_base_url,
            model=self.local_llm_model,
            api_key=self.local_llm_api_key,
            max_dispatch_rounds=self.local_max_dispatch_rounds,
            use_native_tool_calling=self.local_use_native_tool_calling,
            timeout_sec=self.llm_timeout_sec,
            temperature_decision=self.llm_temperature_decision,
            temperature_narrative=self.llm_temperature_narrative,
        )

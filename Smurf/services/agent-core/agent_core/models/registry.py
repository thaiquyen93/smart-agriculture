"""Reads `Settings.model_*` (env `MODEL_*`, see agent_core/config.py) and
returns the matching implementation of each of the 4 ABCs in `base.py`.

This is the ONLY place that branches on `MODEL_*` — callers (worker tools,
future orchestrator wiring) ask for a model through these 4 functions and
never import a baseline/external class directly, mirroring how
`Settings.llm_profile_config()` is the sole LLM_PROFILE branch point
(services/agent-core/CLAUDE.md rule 4, "provider switch is config, not
code" — same principle applied to models instead of LLM providers).

Swapping `MODEL_SOIL_FORECASTER=baseline` -> `fuzzy_branch` in `.env` is
the entire cutover; no agent/tool code changes (05-ml-interfaces.md §2).

NOTE: this module only *reads* `agent_core.config.Settings` — it does not
modify config.py, which already carries the 4 `model_*` fields wired to
`MODEL_*` env vars (present since before this M3 session started).
"""
from __future__ import annotations

from agent_core.config import Settings
from agent_core.models.base import (
    AnomalyDetector,
    PumpHealthDetector,
    SoilMoistureForecaster,
    WaterDemandEstimator,
)
from agent_core.models.baseline.anomaly import AnomalyDetectorBaseline
from agent_core.models.baseline.pump_health import PumpHealthDetectorBaseline
from agent_core.models.baseline.soil_forecaster import SoilForecasterBaseline
from agent_core.models.baseline.water_demand import WaterDemandEstimatorBaseline
from agent_core.models.external.fuzzy_branch_adapter import (
    FuzzyBranchAnomalyDetector,
    FuzzyBranchPumpHealthDetector,
    FuzzyBranchSoilForecaster,
    FuzzyBranchWaterDemandEstimator,
)

_VALID_CHOICES = ("baseline", "fuzzy_branch")


def _unknown_choice_error(env_var: str, value: str) -> ValueError:
    return ValueError(
        f"Unknown {env_var}={value!r} — expected one of {_VALID_CHOICES}. "
        "See docs/agent-core/05-ml-interfaces.md §2."
    )


def get_soil_forecaster(settings: Settings) -> SoilMoistureForecaster:
    choice = settings.model_soil_forecaster
    if choice == "baseline":
        return SoilForecasterBaseline()
    if choice == "fuzzy_branch":
        return FuzzyBranchSoilForecaster()
    raise _unknown_choice_error("MODEL_SOIL_FORECASTER", choice)


def get_water_demand_estimator(settings: Settings) -> WaterDemandEstimator:
    choice = settings.model_water_demand
    if choice == "baseline":
        return WaterDemandEstimatorBaseline()
    if choice == "fuzzy_branch":
        return FuzzyBranchWaterDemandEstimator()
    raise _unknown_choice_error("MODEL_WATER_DEMAND", choice)


def get_pump_health_detector(settings: Settings) -> PumpHealthDetector:
    choice = settings.model_pump_health
    if choice == "baseline":
        return PumpHealthDetectorBaseline()
    if choice == "fuzzy_branch":
        return FuzzyBranchPumpHealthDetector()
    raise _unknown_choice_error("MODEL_PUMP_HEALTH", choice)


def get_anomaly_detector(settings: Settings) -> AnomalyDetector:
    choice = settings.model_anomaly
    if choice == "baseline":
        return AnomalyDetectorBaseline()
    if choice == "fuzzy_branch":
        return FuzzyBranchAnomalyDetector()
    raise _unknown_choice_error("MODEL_ANOMALY", choice)

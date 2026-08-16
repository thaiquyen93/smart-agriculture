"""4 Abstract Base Classes — the hard contract for M3's quantitative ML
layer (docs/agent-core/05-ml-interfaces.md §3).

This is the ONLY file the rest of the codebase (agent tools, workers) and
the `ai-fuzzy-branch` model owner should ever import against. Baseline
implementations live in `agent_core/models/baseline/`, external/pluggable
ones in `agent_core/models/external/`; `agent_core/models/registry.py`
picks between them from `Settings.model_*` (env `MODEL_*`).

Non-negotiable per services/agent-core/CLAUDE.md: this layer produces
numbers, it never interprets them ("LLM proposes, code decides" — the LLM
never computes; only this layer and the Policy Gate do). `model_version`
is mandatory on every result so a human/UI can tell a trained-model answer
apart from a physics/rule fallback — see §4 "Chống cold-start" in the doc.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

# ---------------------------------------------------------------------------
# 1. SoilMoistureForecaster
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ForecastPoint:
    """One predicted point on the forecast horizon."""

    horizon_minutes: int
    predicted_pct: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class ForecastResult:
    points: list[ForecastPoint]
    model_version: str  # e.g. "gbr-0.1" | "physics-fallback"
    is_cold_start: bool
    # Feature name -> importance, for the "why did the model predict this"
    # UI panel. Empty dict is valid (e.g. physics fallback has no features).
    feature_importances: dict[str, float] = field(default_factory=dict)


class SoilMoistureForecaster(ABC):
    """Predicts SOIL_01.soil_moisture at one or more future horizons.

    `history` columns (all present, may contain NaN for missing readings):
    ts, soil_moisture, temperature, humidity, lux, flow_rate.
    """

    @abstractmethod
    def predict(
        self,
        device_id: str,
        horizons_minutes: list[int],
        history: pd.DataFrame,
    ) -> ForecastResult: ...


# ---------------------------------------------------------------------------
# 2. WaterDemandEstimator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CropProfile:
    """Static agronomic config for the crop growing in a zone.

    Superset of the M2 `get_crop_profile` tool's return shape
    (docs/agent-core/02-agents-and-tools.md §C.3) plus the two fields the
    FAO-56 formula needs that the tool doesn't carry yet (`kc`,
    `root_depth_mm`). Loading real values from `config/crop_profiles.yaml`
    into this shape is the Agronomy Agent's job (M2, out of this module's
    scope) — this dataclass only defines what the model layer consumes.
    """

    crop_name: str
    kc: float  # FAO-56 crop coefficient
    root_depth_mm: float  # effective root depth, for deficit->liters
    moisture_optimal_min_pct: float
    moisture_optimal_max_pct: float
    moisture_critical_pct: float
    ph_optimal_min: float
    ph_optimal_max: float
    area_m2: float
    notes_vi: str = ""

    @property
    def moisture_target_pct(self) -> float:
        return (self.moisture_optimal_min_pct + self.moisture_optimal_max_pct) / 2


@dataclass(frozen=True)
class FarmSnapshot:
    """Current physical state of a zone, as needed by WaterDemandEstimator.
    Callers build this from FarmStateStore readings + (optionally) the
    latest SoilMoistureForecaster CI, not from raw evidence — resolving
    evidence_refs -> values is a tool-layer concern (see ADR-003), not this
    module's.
    """

    zone: str
    current_moisture_pct: float
    temp_mean_c: float
    temp_max_c: float
    temp_min_c: float
    lux: float
    day_of_year: int
    observed_at: datetime
    moisture_ci_low_pct: float | None = None
    moisture_ci_high_pct: float | None = None


@dataclass(frozen=True)
class WaterDemandResult:
    volume_liters: float
    confidence_low: float
    confidence_high: float
    et0_mm_day: float
    method: str  # e.g. "hargreaves-samani+fao56-kc"
    model_version: str
    # Must sum to volume_liters: deficit_liters + etc_liters + efficiency_loss_liters
    breakdown: dict[str, float] = field(default_factory=dict)


class WaterDemandEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        zone: str,
        current_state: FarmSnapshot,
        crop_profile: CropProfile,
        horizon_hours: int = 6,
    ) -> WaterDemandResult: ...


# ---------------------------------------------------------------------------
# 3. PumpHealthDetector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PumpHealthResult:
    status: str  # OK | DEGRADED | FAULT | UNKNOWN
    efficiency_lpm_per_watt: float
    baseline_efficiency: float
    deviation_pct: float
    symptom: str  # NONE | FILTER_CLOG | HIGH_POWER_NO_FLOW | INTERMITTENT | UNKNOWN
    model_version: str


class PumpHealthDetector(ABC):
    """`history` columns: ts, flow_rate, power (PUMP_01 raw readings over
    the trailing window, typically 24h)."""

    @abstractmethod
    def diagnose(self, device_id: str, history: pd.DataFrame) -> PumpHealthResult: ...


# ---------------------------------------------------------------------------
# 4. AnomalyDetector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Anomaly:
    anomaly_type: str
    device_id: str
    score_0_1: float
    detected_at: datetime
    model_version: str
    contributing_features: list[str] = field(default_factory=list)


class AnomalyDetector(ABC):
    """`windows` is the ~6h sliding window of topic_p aggregates across all
    6 devices, one row per timestamp, columns include (at least)
    soil_moisture_avg, temperature_avg, humidity_avg, flow_rate_avg,
    power_avg, ph_avg, level_avg, lux_avg and their _trend counterparts,
    plus per-device raw columns needed by the 3 cross-device rules
    (pump_flow_rate, soil_moisture, tank_level, sun_lux,
    weather_temperature) — see baseline/anomaly.py docstring for the exact
    column contract.
    """

    @abstractmethod
    def detect(self, zone: str, windows: pd.DataFrame) -> list[Anomaly]: ...

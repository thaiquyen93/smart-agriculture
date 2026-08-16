"""M3 quantitative ML layer — see docs/agent-core/05-ml-interfaces.md.

Re-exports the 4 ABCs + their dataclasses from `base.py`, the 4 baseline
implementations, and the `registry.get_*` functions so callers can do
`from agent_core.models import get_soil_forecaster` instead of reaching
into submodules directly.
"""
from __future__ import annotations

from agent_core.models.base import (
    Anomaly,
    AnomalyDetector,
    CropProfile,
    FarmSnapshot,
    ForecastPoint,
    ForecastResult,
    PumpHealthDetector,
    PumpHealthResult,
    SoilMoistureForecaster,
    WaterDemandEstimator,
    WaterDemandResult,
)
from agent_core.models.baseline.anomaly import AnomalyDetectorBaseline
from agent_core.models.baseline.pump_health import PumpHealthDetectorBaseline
from agent_core.models.baseline.soil_forecaster import SoilForecasterBaseline
from agent_core.models.baseline.water_demand import WaterDemandEstimatorBaseline
from agent_core.models.registry import (
    get_anomaly_detector,
    get_pump_health_detector,
    get_soil_forecaster,
    get_water_demand_estimator,
)

__all__ = [
    # ABCs
    "SoilMoistureForecaster",
    "WaterDemandEstimator",
    "PumpHealthDetector",
    "AnomalyDetector",
    # dataclasses
    "ForecastPoint",
    "ForecastResult",
    "CropProfile",
    "FarmSnapshot",
    "WaterDemandResult",
    "PumpHealthResult",
    "Anomaly",
    # baseline implementations
    "SoilForecasterBaseline",
    "WaterDemandEstimatorBaseline",
    "PumpHealthDetectorBaseline",
    "AnomalyDetectorBaseline",
    # registry
    "get_soil_forecaster",
    "get_water_demand_estimator",
    "get_pump_health_detector",
    "get_anomaly_detector",
]

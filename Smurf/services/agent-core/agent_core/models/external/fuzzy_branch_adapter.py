"""Stub adapters for the `ai-fuzzy-branch` team's models (05-ml-interfaces.md
§5). Each class implements one of the 4 ABCs from `agent_core.models.base`
so `MODEL_*=fuzzy_branch` never breaks imports/registry wiring — it just
raises `NotImplementedError` at call time until the real model is plugged
in here.

To cut over: replace one class body below with the real implementation (or
delete the stub and import the fuzzy-branch package directly), keeping the
method signature identical to its ABC. No other file needs to change —
`registry.py` already points `MODEL_*=fuzzy_branch` at these classes.
"""
from __future__ import annotations

import pandas as pd

from agent_core.models.base import (
    Anomaly,
    AnomalyDetector,
    CropProfile,
    FarmSnapshot,
    ForecastResult,
    PumpHealthDetector,
    PumpHealthResult,
    SoilMoistureForecaster,
    WaterDemandEstimator,
    WaterDemandResult,
)

_NOT_WIRED = (
    "Cắm model ai-fuzzy-branch tại đây — xem docs/agent-core/05-ml-interfaces.md §5. "
    "{cls} chưa có implementation thật, chỉ là stub giữ chỗ cho registry."
)


class FuzzyBranchSoilForecaster(SoilMoistureForecaster):
    def predict(
        self,
        device_id: str,
        horizons_minutes: list[int],
        history: pd.DataFrame,
    ) -> ForecastResult:
        raise NotImplementedError(_NOT_WIRED.format(cls=type(self).__name__))


class FuzzyBranchWaterDemandEstimator(WaterDemandEstimator):
    def estimate(
        self,
        zone: str,
        current_state: FarmSnapshot,
        crop_profile: CropProfile,
        horizon_hours: int = 6,
    ) -> WaterDemandResult:
        raise NotImplementedError(_NOT_WIRED.format(cls=type(self).__name__))


class FuzzyBranchPumpHealthDetector(PumpHealthDetector):
    def diagnose(self, device_id: str, history: pd.DataFrame) -> PumpHealthResult:
        raise NotImplementedError(_NOT_WIRED.format(cls=type(self).__name__))


class FuzzyBranchAnomalyDetector(AnomalyDetector):
    def detect(self, zone: str, windows: pd.DataFrame) -> list[Anomaly]:
        raise NotImplementedError(_NOT_WIRED.format(cls=type(self).__name__))

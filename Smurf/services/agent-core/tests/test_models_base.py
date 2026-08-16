"""Tests for the M3 ABC contract itself (agent_core/models/base.py) —
none of the 4 ABCs can be instantiated directly, and the dataclasses have
the shape docs/agent-core/05-ml-interfaces.md §3 specifies. No sklearn/
pandas math here, that's covered per-model in the other test_models_*.py
files; this file only guards the contract from silently drifting.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pandas as pd
import pytest

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


# --- ABCs cannot be instantiated directly -----------------------------------


@pytest.mark.parametrize(
    "abc_cls",
    [SoilMoistureForecaster, WaterDemandEstimator, PumpHealthDetector, AnomalyDetector],
)
def test_abc_cannot_be_instantiated_directly(abc_cls):
    with pytest.raises(TypeError):
        abc_cls()


def test_incomplete_subclass_still_abstract():
    """A subclass that doesn't implement the abstract method stays abstract
    — guards against someone accidentally dropping @abstractmethod."""

    class IncompleteForecaster(SoilMoistureForecaster):
        pass

    with pytest.raises(TypeError):
        IncompleteForecaster()


def test_complete_subclass_is_instantiable():
    class MinimalForecaster(SoilMoistureForecaster):
        def predict(self, device_id, horizons_minutes, history):
            return ForecastResult(points=[], model_version="test", is_cold_start=True)

    instance = MinimalForecaster()
    result = instance.predict("SOIL_01", [15], pd.DataFrame())
    assert result.model_version == "test"


# --- dataclasses: shape + frozen immutability --------------------------------


def test_forecast_result_shape_and_defaults():
    point = ForecastPoint(horizon_minutes=15, predicted_pct=30.0, ci_low=27.0, ci_high=33.0)
    result = ForecastResult(points=[point], model_version="physics-fallback", is_cold_start=True)
    assert result.points == [point]
    assert result.feature_importances == {}  # default_factory
    with pytest.raises(FrozenInstanceError):
        result.is_cold_start = False


def test_crop_profile_moisture_target_pct_is_midpoint():
    profile = CropProfile(
        crop_name="Cam",
        kc=0.9,
        root_depth_mm=300.0,
        moisture_optimal_min_pct=40.0,
        moisture_optimal_max_pct=60.0,
        moisture_critical_pct=20.0,
        ph_optimal_min=5.5,
        ph_optimal_max=6.5,
        area_m2=100.0,
    )
    assert profile.moisture_target_pct == pytest.approx(50.0)
    assert profile.notes_vi == ""  # default
    with pytest.raises(FrozenInstanceError):
        profile.kc = 1.0


def test_farm_snapshot_ci_fields_optional():
    snap = FarmSnapshot(
        zone="ZONE_A",
        current_moisture_pct=32.0,
        temp_mean_c=28.0,
        temp_max_c=33.0,
        temp_min_c=24.0,
        lux=45000.0,
        day_of_year=228,
        observed_at=datetime.now(timezone.utc),
    )
    assert snap.moisture_ci_low_pct is None
    assert snap.moisture_ci_high_pct is None


def test_water_demand_result_breakdown_default_empty():
    result = WaterDemandResult(
        volume_liters=100.0,
        confidence_low=85.0,
        confidence_high=115.0,
        et0_mm_day=4.2,
        method="hargreaves-samani+fao56-kc",
        model_version="water-demand-baseline-0.1",
    )
    assert result.breakdown == {}


def test_pump_health_result_fields():
    result = PumpHealthResult(
        status="DEGRADED",
        efficiency_lpm_per_watt=0.02,
        baseline_efficiency=0.033,
        deviation_pct=-40.0,
        symptom="FILTER_CLOG",
        model_version="pump-health-baseline-0.1",
    )
    assert result.status == "DEGRADED"
    assert result.symptom == "FILTER_CLOG"
    with pytest.raises(FrozenInstanceError):
        result.status = "OK"


def test_anomaly_contributing_features_default_empty_list():
    anomaly = Anomaly(
        anomaly_type="MULTIVARIATE_OUTLIER",
        device_id="ZONE_A",
        score_0_1=0.8,
        detected_at=datetime.now(timezone.utc),
        model_version="isoforest-0.1",
    )
    assert anomaly.contributing_features == []

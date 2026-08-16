"""Tests for agent_core/models/registry.py — the single MODEL_* branch
point (docs/agent-core/05-ml-interfaces.md §2, mirrors how
Settings.llm_profile_config() is the sole LLM_PROFILE branch point).

Uses SimpleNamespace instead of a real Settings instance (same pattern as
tests/test_field_iot_tools.py's `settings` fixture) — registry.py only
reads 4 attributes, so a real .env/Settings.from_env() isn't needed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

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
from agent_core.models.registry import (
    get_anomaly_detector,
    get_pump_health_detector,
    get_soil_forecaster,
    get_water_demand_estimator,
)


def _settings(**overrides) -> SimpleNamespace:
    defaults = dict(
        model_soil_forecaster="baseline",
        model_water_demand="baseline",
        model_pump_health="baseline",
        model_anomaly="baseline",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# --- baseline: default wiring ------------------------------------------------


def test_get_soil_forecaster_baseline():
    assert isinstance(get_soil_forecaster(_settings()), SoilForecasterBaseline)


def test_get_water_demand_estimator_baseline():
    assert isinstance(get_water_demand_estimator(_settings()), WaterDemandEstimatorBaseline)


def test_get_pump_health_detector_baseline():
    assert isinstance(get_pump_health_detector(_settings()), PumpHealthDetectorBaseline)


def test_get_anomaly_detector_baseline():
    assert isinstance(get_anomaly_detector(_settings()), AnomalyDetectorBaseline)


# --- fuzzy_branch: cutover wiring, stub raises at call time not at get_*() --


def test_get_soil_forecaster_fuzzy_branch():
    forecaster = get_soil_forecaster(_settings(model_soil_forecaster="fuzzy_branch"))
    assert isinstance(forecaster, FuzzyBranchSoilForecaster)
    with pytest.raises(NotImplementedError):
        forecaster.predict("SOIL_01", [15], None)


def test_get_water_demand_estimator_fuzzy_branch():
    estimator = get_water_demand_estimator(_settings(model_water_demand="fuzzy_branch"))
    assert isinstance(estimator, FuzzyBranchWaterDemandEstimator)
    with pytest.raises(NotImplementedError):
        estimator.estimate("ZONE_A", None, None)


def test_get_pump_health_detector_fuzzy_branch():
    detector = get_pump_health_detector(_settings(model_pump_health="fuzzy_branch"))
    assert isinstance(detector, FuzzyBranchPumpHealthDetector)
    with pytest.raises(NotImplementedError):
        detector.diagnose("PUMP_01", None)


def test_get_anomaly_detector_fuzzy_branch():
    detector = get_anomaly_detector(_settings(model_anomaly="fuzzy_branch"))
    assert isinstance(detector, FuzzyBranchAnomalyDetector)
    with pytest.raises(NotImplementedError):
        detector.detect("ZONE_A", None)


# --- unknown choice: fail fast, not silent None -----------------------------


@pytest.mark.parametrize(
    "getter, override_key",
    [
        (get_soil_forecaster, "model_soil_forecaster"),
        (get_water_demand_estimator, "model_water_demand"),
        (get_pump_health_detector, "model_pump_health"),
        (get_anomaly_detector, "model_anomaly"),
    ],
)
def test_unknown_choice_raises_value_error(getter, override_key):
    with pytest.raises(ValueError):
        getter(_settings(**{override_key: "bogus"}))


def test_each_model_env_var_is_independent():
    """One MODEL_* set to fuzzy_branch doesn't affect the other 3 — each
    getter reads only its own Settings field."""
    settings = _settings(model_pump_health="fuzzy_branch")
    assert isinstance(get_soil_forecaster(settings), SoilForecasterBaseline)
    assert isinstance(get_water_demand_estimator(settings), WaterDemandEstimatorBaseline)
    assert isinstance(get_pump_health_detector(settings), FuzzyBranchPumpHealthDetector)
    assert isinstance(get_anomaly_detector(settings), AnomalyDetectorBaseline)

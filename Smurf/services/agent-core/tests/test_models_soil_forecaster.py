"""Tests for SoilForecasterBaseline (docs/agent-core/05-ml-interfaces.md
§3.1, §4 "Chống cold-start"). Style follows tests/test_field_iot_tools.py:
direct calls, no LLM involved, one synthetic-telemetry fixture shared by the
"enough data" tests plus small targeted frames per edge case."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from agent_core.models.base import ForecastResult
from agent_core.models.baseline.soil_forecaster import SoilForecasterBaseline

DEVICE_ID = "SOIL_01"


def _synthetic_history(n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """1-minute telemetry: soil_moisture follows a diurnal decay (faster
    when hot/sunny, mirroring the physics fallback's own formula) plus
    random irrigation bursts that bump moisture back up. That irrigation
    signal is exactly what lag/flow-rate features let a GBR track that a
    smooth decay-only formula or a naive no-op cannot."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-08-01 00:00:00")
    ts = pd.date_range(start, periods=n, freq="1min")
    hour_frac = (ts.hour + ts.minute / 60.0).to_numpy()

    temperature = 26.0 + 6.0 * np.sin(2 * np.pi * (hour_frac - 9) / 24) + rng.normal(0, 0.3, n)
    humidity = np.clip(
        65.0 - 15.0 * np.sin(2 * np.pi * (hour_frac - 9) / 24) + rng.normal(0, 1.0, n), 20, 95
    )
    sun = np.maximum(0.0, np.sin(2 * np.pi * (hour_frac - 6) / 24)) ** 1.2
    lux = np.clip(40000.0 * sun + rng.normal(0, 500, n), 0, None)

    flow_rate = np.zeros(n)
    n_events = max(1, n // 400)
    starts = rng.choice(np.arange(30, n - 30), size=n_events, replace=False)
    for s in starts:
        dur = int(rng.integers(5, 15))
        flow_rate[s : s + dur] = rng.uniform(8, 15)

    soil = np.zeros(n)
    soil[0] = 45.0
    for i in range(1, n):
        decay_per_min = 3.0 * (temperature[i] / 25.0) * (lux[i] / 50000.0) / 1440.0
        gain = flow_rate[i] * 0.15
        soil[i] = soil[i - 1] - decay_per_min + gain + rng.normal(0, 0.05)
        soil[i] = float(np.clip(soil[i], 5.0, 60.0))

    return pd.DataFrame(
        {
            "ts": ts,
            "soil_moisture": soil,
            "temperature": temperature,
            "humidity": humidity,
            "lux": lux,
            "flow_rate": flow_rate,
        }
    )


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return _synthetic_history()


@pytest.fixture
def model() -> SoilForecasterBaseline:
    return SoilForecasterBaseline()


# --- sufficient data -> GBR branch --------------------------------------------


def test_predict_with_sufficient_history_uses_gbr(model, history):
    result = model.predict(DEVICE_ID, [15, 30, 60], history)

    assert isinstance(result, ForecastResult)
    assert result.is_cold_start is False
    assert result.model_version == "gbr-0.1"
    assert result.feature_importances != {}
    assert len(result.points) == 3
    for point in result.points:
        assert 0.0 <= point.predicted_pct <= 100.0
        assert 0.0 <= point.ci_low <= point.ci_high <= 100.0


def test_predict_multiple_horizons_order_preserved(model, history):
    horizons = [15, 30, 60]
    result = model.predict(DEVICE_ID, horizons, history)

    assert [p.horizon_minutes for p in result.points] == horizons
    assert len(result.points) == len(horizons)


# --- M3.1 acceptance: GBR beats naive baselines on held-out points -----------


def _manual_physics_prediction(current_moisture: float, temp_now: float, lux_now: float, horizon: int) -> float:
    """Mirrors the *documented* physics-fallback formula (05-ml-interfaces
    §3.1 / this module's docstring) independently of the implementation --
    this test must exercise the contract, not call the private method."""
    decay_rate_pct_per_day = 3.0 * (temp_now / 25.0) * (lux_now / 50000.0)
    predicted = current_moisture - decay_rate_pct_per_day * (horizon / 1440.0)
    return float(min(max(predicted, 0.0), 100.0))


def test_gbr_beats_naive_baselines_on_holdout(model, history):
    """M3.1 acceptance: model's error on held-out points beats both a
    naive no-op prediction and the physics fallback applied by hand on the
    same points."""
    n = len(history)
    train_size = int(n * 0.8)  # 80/20 train/holdout split
    horizon = 15
    window_size = 400  # bound each walk-forward GBR fit's cost

    cutoffs = list(range(train_size, n - horizon, 20))[:10]
    assert len(cutoffs) >= 5  # sanity: fixture large enough for a real holdout sweep

    model_errors = []
    fallback_errors = []
    noop_errors = []

    for cutoff in cutoffs:
        # Train only on data strictly before `cutoff` -- no peeking at the
        # holdout point being scored.
        window = history.iloc[max(0, cutoff - window_size) : cutoff]
        actual = float(history.iloc[cutoff + horizon]["soil_moisture"])

        result = model.predict(DEVICE_ID, [horizon], window)
        predicted = result.points[0].predicted_pct
        model_errors.append(abs(predicted - actual))

        last_row = window.iloc[-1]
        fallback_pred = _manual_physics_prediction(
            float(last_row["soil_moisture"]),
            float(last_row["temperature"]),
            float(last_row["lux"]),
            horizon,
        )
        fallback_errors.append(abs(fallback_pred - actual))

        noop_errors.append(abs(float(last_row["soil_moisture"]) - actual))

    mae_model = sum(model_errors) / len(model_errors)
    mae_fallback = sum(fallback_errors) / len(fallback_errors)
    mae_noop = sum(noop_errors) / len(noop_errors)

    assert mae_model < mae_noop
    assert mae_model <= mae_fallback


# --- cold start -------------------------------------------------------------------


def test_predict_empty_history_is_cold_start(model):
    empty = pd.DataFrame(columns=["ts", "soil_moisture", "temperature", "humidity", "lux", "flow_rate"])
    result = model.predict(DEVICE_ID, [15, 30], empty)

    assert result.is_cold_start is True
    assert result.model_version == "physics-fallback"
    assert len(result.points) == 2
    for point in result.points:
        assert 0.0 <= point.predicted_pct <= 100.0
        assert 0.0 <= point.ci_low <= point.ci_high <= 100.0


def test_predict_below_min_train_samples_is_cold_start(model, history):
    small = history.iloc[:50]
    result = model.predict(DEVICE_ID, [15], small)

    assert result.is_cold_start is True
    assert result.model_version == "physics-fallback"
    assert len(result.points) == 1
    assert 0.0 <= result.points[0].predicted_pct <= 100.0


# --- missing/garbage columns never raise -------------------------------------------


def test_predict_missing_columns_does_not_raise(model):
    n = 300
    ts = pd.date_range("2026-08-01", periods=n, freq="1min")
    partial = pd.DataFrame({"ts": ts, "soil_moisture": np.full(n, 32.0)})  # no temperature/humidity/lux/flow_rate

    result = model.predict(DEVICE_ID, [15, 60], partial)

    assert isinstance(result, ForecastResult)
    assert len(result.points) == 2
    for point in result.points:
        assert 0.0 <= point.predicted_pct <= 100.0


def test_predict_all_nan_soil_moisture_does_not_raise(model):
    n = 300
    ts = pd.date_range("2026-08-01", periods=n, freq="1min")
    garbage = pd.DataFrame(
        {
            "ts": ts,
            "soil_moisture": [np.nan] * n,
            "temperature": [np.nan] * n,
            "humidity": [np.nan] * n,
            "lux": [np.nan] * n,
            "flow_rate": [np.nan] * n,
        }
    )

    result = model.predict(DEVICE_ID, [15], garbage)

    assert isinstance(result, ForecastResult)
    assert result.is_cold_start is True
    assert result.model_version == "physics-fallback"
    # DEFAULT_MOISTURE_PCT=30.0, DEFAULT_TEMP_C=28.0, DEFAULT_LUX=30000.0 (no
    # usable data at all) with the documented decay formula applied over the
    # 15-minute horizon -- not just the bare default.
    expected = _manual_physics_prediction(30.0, 28.0, 30000.0, 15)
    assert result.points[0].predicted_pct == pytest.approx(expected)


def test_predict_none_history_does_not_raise(model):
    result = model.predict(DEVICE_ID, [15], None)

    assert isinstance(result, ForecastResult)
    assert result.is_cold_start is True
    assert len(result.points) == 1

"""Tests for the baseline WaterDemandEstimator (roadmap M3.2), per
docs/agent-core/05-ml-interfaces.md §3.2. Mirrors the style of
tests/test_field_iot_tools.py: plain function-level tests, fixtures for the
shared FarmSnapshot/CropProfile inputs, no LLM involved.

Test 1 independently re-derives Ra/ET0 by hand (not by importing the
module's internal helpers) so the Hargreaves-Samani arithmetic is checked
against a second, separately-written implementation of the same formula.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from agent_core.models.base import CropProfile, FarmSnapshot
from agent_core.models.baseline.water_demand import WaterDemandEstimatorBaseline

LATITUDE_RAD = math.radians(10.8)
LUX_CLEAR_SKY_REF = 100_000.0


def _crop_profile(**overrides) -> CropProfile:
    defaults = dict(
        crop_name="tomato",
        kc=1.15,
        root_depth_mm=300.0,
        moisture_optimal_min_pct=60.0,
        moisture_optimal_max_pct=80.0,
        moisture_critical_pct=30.0,
        ph_optimal_min=6.0,
        ph_optimal_max=6.8,
        area_m2=50.0,
        notes_vi="",
    )
    defaults.update(overrides)
    return CropProfile(**defaults)


def _snapshot(**overrides) -> FarmSnapshot:
    defaults = dict(
        zone="Z1",
        current_moisture_pct=50.0,
        temp_mean_c=28.0,
        temp_max_c=33.0,
        temp_min_c=24.0,
        lux=60_000.0,
        day_of_year=180,
        observed_at=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return FarmSnapshot(**defaults)


@pytest.fixture
def estimator() -> WaterDemandEstimatorBaseline:
    return WaterDemandEstimatorBaseline()


# --- 1. ET0 hand-derivation --------------------------------------------------


def test_et0_matches_hand_derived_hargreaves_samani(estimator):
    day_of_year = 180
    temp_mean_c = 28.0
    temp_max_c = 33.0
    temp_min_c = 24.0
    lux = 60_000.0

    # Independently re-derive Ra/ET0 by hand, per FAO-56 Annex 1 +
    # Hargreaves-Samani, written out again here (no import of internal
    # helpers) so this is a genuine cross-check of the module's arithmetic.
    solar_declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    sunset_hour_angle = math.acos(
        max(-1.0, min(1.0, -math.tan(LATITUDE_RAD) * math.tan(solar_declination)))
    )
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    ra_theoretical = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (
            sunset_hour_angle * math.sin(LATITUDE_RAD) * math.sin(solar_declination)
            + math.cos(LATITUDE_RAD) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
    )
    lux_factor = max(0.1, min(1.2, lux / LUX_CLEAR_SKY_REF))
    ra = ra_theoretical * lux_factor
    expected_et0 = 0.0023 * ra * (temp_mean_c + 17.8) * math.sqrt(temp_max_c - temp_min_c)

    snapshot = _snapshot(
        day_of_year=day_of_year,
        temp_mean_c=temp_mean_c,
        temp_max_c=temp_max_c,
        temp_min_c=temp_min_c,
        lux=lux,
    )
    result = estimator.estimate("Z1", snapshot, _crop_profile())

    assert result.et0_mm_day == pytest.approx(expected_et0, rel=1e-6)


# --- 2. breakdown must sum exactly to volume_liters --------------------------


def test_breakdown_sums_to_volume_liters(estimator):
    result = estimator.estimate("Z1", _snapshot(), _crop_profile())

    total = (
        result.breakdown["deficit_liters"]
        + result.breakdown["etc_liters"]
        + result.breakdown["efficiency_loss_liters"]
    )
    assert total == pytest.approx(result.volume_liters, rel=1e-9)


# --- 3. moisture already at/above target -> zero deficit ---------------------


def test_no_deficit_when_moisture_at_or_above_target(estimator):
    crop = _crop_profile(moisture_optimal_min_pct=60.0, moisture_optimal_max_pct=80.0)
    snapshot = _snapshot(current_moisture_pct=90.0)  # above target (70)

    result = estimator.estimate("Z1", snapshot, crop)

    assert result.breakdown["deficit_liters"] == pytest.approx(0.0, abs=1e-9)


# --- 4. no forecaster CI on the snapshot -> still valid CI --------------------


def test_confidence_interval_valid_without_forecaster_ci(estimator):
    snapshot = _snapshot(moisture_ci_low_pct=None, moisture_ci_high_pct=None)

    result = estimator.estimate("Z1", snapshot, _crop_profile())

    assert result.confidence_low <= result.volume_liters <= result.confidence_high


# --- 5. forecaster CI present -> valid, positive confidence bounds -----------


def test_confidence_interval_valid_with_forecaster_ci(estimator):
    snapshot = _snapshot(moisture_ci_low_pct=48.0, moisture_ci_high_pct=52.0)

    result = estimator.estimate("Z1", snapshot, _crop_profile())

    assert result.confidence_low > 0
    assert result.confidence_low <= result.volume_liters <= result.confidence_high


def test_narrower_forecaster_ci_yields_narrower_confidence_band(estimator):
    narrow = _snapshot(moisture_ci_low_pct=49.0, moisture_ci_high_pct=51.0)
    wide = _snapshot(moisture_ci_low_pct=30.0, moisture_ci_high_pct=70.0)
    crop = _crop_profile()

    narrow_result = estimator.estimate("Z1", narrow, crop)
    wide_result = estimator.estimate("Z1", wide, crop)

    narrow_width = narrow_result.confidence_high - narrow_result.confidence_low
    wide_width = wide_result.confidence_high - wide_result.confidence_low
    assert narrow_width < wide_width


# --- 6. etc_liters scales linearly with horizon_hours -------------------------


def test_etc_liters_scales_linearly_with_horizon(estimator):
    crop = _crop_profile()
    snapshot = _snapshot()

    short = estimator.estimate("Z1", snapshot, crop, horizon_hours=3)
    long_ = estimator.estimate("Z1", snapshot, crop, horizon_hours=12)

    assert short.breakdown["etc_liters"] > 0
    ratio = long_.breakdown["etc_liters"] / short.breakdown["etc_liters"]
    assert ratio == pytest.approx(12 / 3, rel=1e-9)
    # deficit_liters (moisture-only) must not change with horizon.
    assert short.breakdown["deficit_liters"] == pytest.approx(long_.breakdown["deficit_liters"], rel=1e-9)


def test_zero_horizon_hours_has_zero_etc_liters(estimator):
    result = estimator.estimate("Z1", _snapshot(), _crop_profile(), horizon_hours=0)

    assert result.breakdown["etc_liters"] == pytest.approx(0.0, abs=1e-9)


# --- 7. noisy sensor data: Tmax < Tmin ----------------------------------------


def test_tmax_less_than_tmin_does_not_raise_and_stays_nonnegative(estimator):
    snapshot = _snapshot(temp_max_c=20.0, temp_min_c=25.0, temp_mean_c=22.0)

    result = estimator.estimate("Z1", snapshot, _crop_profile())

    assert result.et0_mm_day >= 0.0
    assert result.volume_liters >= 0.0

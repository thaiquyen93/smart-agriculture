"""Baseline `WaterDemandEstimator` — FAO-56 Hargreaves-Samani ET0/ETc model
(docs/agent-core/05-ml-interfaces.md §3.2). Physics, not a hardcoded
`deficit * 15.0` threshold: derives extraterrestrial radiation (Ra) from
day-of-year astronomy, corrects it against the actual `SUN_01.lux` reading,
runs it through Hargreaves-Samani for ET0, applies the crop coefficient for
ETc, and combines that with the current moisture deficit to get a liters
figure with an explicit component breakdown and a propagated confidence
interval.

Only this module implements the estimator; `agent_core/models/base.py`
(the ABC contract) is not touched here.
"""
from __future__ import annotations

import math

from agent_core.models.base import (
    CropProfile,
    FarmSnapshot,
    WaterDemandEstimator,
    WaterDemandResult,
)

# Approximate latitude for Vietnam (used for the Ra astronomy formula).
_LATITUDE_RAD = math.radians(10.8)

# Lux reading at solar noon under a clear sky — reference point for scaling
# the theoretical (clear-sky) Ra down/up to what the sensor actually saw.
LUX_CLEAR_SKY_REF = 100_000.0

# Drip/sprinkler irrigation efficiency: fraction of delivered water that
# actually reaches the root zone (the rest is lost to evaporation/runoff).
IRRIGATION_EFFICIENCY = 0.85

# Relative error assumed on the Hargreaves-Samani ET0 estimate itself.
_ET0_ERROR_FRAC = 0.15

# Default relative error on the moisture deficit when no forecaster
# confidence interval is available on the snapshot.
_DEFAULT_MOISTURE_ERROR_FRAC = 0.10

_METHOD = "hargreaves-samani+fao56-kc"
_MODEL_VERSION = "water-demand-baseline-0.1"


def _extraterrestrial_radiation_mj_m2_day(day_of_year: int) -> float:
    """Ra_theoretical, FAO-56 Annex 1 (MJ/m^2/day), clear-sky / no lux
    correction applied yet."""
    solar_declination = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    sunset_hour_angle_arg = -math.tan(_LATITUDE_RAD) * math.tan(solar_declination)
    # Clamp into [-1, 1] to guard the arccos domain for extreme
    # latitude/season combinations (polar day/night edge cases).
    sunset_hour_angle_arg = max(-1.0, min(1.0, sunset_hour_angle_arg))
    sunset_hour_angle = math.acos(sunset_hour_angle_arg)
    sunset_hour_angle = max(sunset_hour_angle, 0.0)

    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)

    ra_theoretical = (
        (24 * 60 / math.pi)
        * 0.0820
        * dr
        * (
            sunset_hour_angle * math.sin(_LATITUDE_RAD) * math.sin(solar_declination)
            + math.cos(_LATITUDE_RAD) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
    )
    return max(ra_theoretical, 0.0)


def _lux_corrected_ra(ra_theoretical: float, lux: float) -> float:
    lux_factor = max(0.1, min(1.2, lux / LUX_CLEAR_SKY_REF))
    return ra_theoretical * lux_factor


def _et0_mm_day(ra: float, temp_mean_c: float, temp_max_c: float, temp_min_c: float) -> float:
    tmax, tmin = temp_max_c, temp_min_c
    if tmax < tmin:
        tmax, tmin = tmin, tmax
    et0 = 0.0023 * ra * (temp_mean_c + 17.8) * math.sqrt(max(tmax - tmin, 0.0))
    return max(et0, 0.0)


class WaterDemandEstimatorBaseline(WaterDemandEstimator):
    """Physics baseline: Hargreaves-Samani ET0 -> FAO-56 Kc -> ETc, combined
    with the current moisture deficit, converted to liters via the crop's
    root depth and zone area, then inflated by irrigation-system losses."""

    def estimate(
        self,
        zone: str,
        current_state: FarmSnapshot,
        crop_profile: CropProfile,
        horizon_hours: int = 6,
    ) -> WaterDemandResult:
        ra_theoretical = _extraterrestrial_radiation_mj_m2_day(current_state.day_of_year)
        ra = _lux_corrected_ra(ra_theoretical, current_state.lux)

        et0_mm_day = _et0_mm_day(
            ra,
            current_state.temp_mean_c,
            current_state.temp_max_c,
            current_state.temp_min_c,
        )
        etc_mm_day = et0_mm_day * crop_profile.kc

        area_m2 = max(crop_profile.area_m2, 0.0)
        root_depth_mm = max(crop_profile.root_depth_mm, 0.0)
        clamped_horizon_hours = max(horizon_hours, 0)

        deficit_pct = max(0.0, crop_profile.moisture_target_pct - current_state.current_moisture_pct)
        deficit_liters = (deficit_pct / 100.0) * root_depth_mm * area_m2
        etc_liters = etc_mm_day * (clamped_horizon_hours / 24.0) * area_m2

        subtotal = deficit_liters + etc_liters
        efficiency_loss_liters = subtotal * (1.0 / IRRIGATION_EFFICIENCY - 1.0)
        volume_liters = subtotal + efficiency_loss_liters

        if current_state.moisture_ci_low_pct is not None and current_state.moisture_ci_high_pct is not None:
            moisture_ci_width_pct = current_state.moisture_ci_high_pct - current_state.moisture_ci_low_pct
            moisture_error_frac = min(
                moisture_ci_width_pct / max(current_state.current_moisture_pct, 1.0) / 2.0,
                0.5,
            )
        else:
            moisture_error_frac = _DEFAULT_MOISTURE_ERROR_FRAC

        combined_error_frac = min(
            (_ET0_ERROR_FRAC**2 + moisture_error_frac**2) ** 0.5,
            0.9,
        )
        confidence_low = volume_liters * (1.0 - combined_error_frac)
        confidence_high = volume_liters * (1.0 + combined_error_frac)

        return WaterDemandResult(
            volume_liters=volume_liters,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            et0_mm_day=et0_mm_day,
            method=_METHOD,
            model_version=_MODEL_VERSION,
            breakdown={
                "deficit_liters": deficit_liters,
                "etc_liters": etc_liters,
                "efficiency_loss_liters": efficiency_loss_liters,
            },
        )

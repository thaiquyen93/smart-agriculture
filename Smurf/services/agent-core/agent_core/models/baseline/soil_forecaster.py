"""Baseline `SoilMoistureForecaster` (docs/agent-core/05-ml-interfaces.md
§3.1, §4 "Chống cold-start").

Two-tier strategy, per the doc and `services/agent-core/CLAUDE.md`'s
"model layer produces numbers, never raises" rule:

1. **Main branch** — one `GradientBoostingRegressor` per requested horizon,
   trained on-the-fly from `history` (lag/trend/rolling/time-of-day
   features). Only used once there is enough history (`MIN_TRAIN_SAMPLES`)
   and, per horizon, enough (X, y) rows survive feature/label construction
   (`MIN_HORIZON_TRAIN_SAMPLES`).
2. **Physics fallback** (`_physics_fallback`) — a small self-contained
   linear evaporation-decay proxy. It is deliberately NOT the FAO-56
   Hargreaves-Samani formula (that lives in `WaterDemandEstimator`,
   docs §3.2) — this is a cheap "moisture decays faster when hot/sunny"
   heuristic good enough to cover cold-start and any unexpected failure in
   the GBR branch without ever raising out of `predict()`.

`model_version` always tells the caller which tier produced a given
result ("gbr-0.1" | "physics-fallback"), and `is_cold_start` mirrors that
at the whole-`ForecastResult` level, per §4 of the doc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from agent_core.models.base import ForecastPoint, ForecastResult, SoilMoistureForecaster

# Below this many non-null soil_moisture readings in `history`, skip the GBR
# branch entirely and go straight to the physics fallback for every horizon.
MIN_TRAIN_SAMPLES = 200

# Below this many usable (X, y) rows for a *specific* horizon after feature
# engineering + dropna, that horizon alone falls back to physics (the other
# horizons may still succeed with GBR).
MIN_HORIZON_TRAIN_SAMPLES = 50

# Defaults used by the physics fallback when `history` is empty or missing
# the relevant column entirely (never raise, always return something sane).
DEFAULT_MOISTURE_PCT = 30.0
DEFAULT_TEMP_C = 28.0
DEFAULT_LUX = 30000.0

# Reference condition the physics decay-rate formula is calibrated against.
_REFERENCE_TEMP_C = 25.0
_REFERENCE_LUX = 50000.0
_REFERENCE_DECAY_PCT_PER_DAY = 3.0

FEATURE_COLUMNS: list[str] = [
    "lag_1",
    "lag_5",
    "lag_15",
    "lag_30",
    "trend",
    "temp_now",
    "humidity_now",
    "lux_now",
    "temp_15m_avg",
    "humidity_15m_avg",
    "lux_15m_avg",
    "flow_30m_cum",
    "hour_sin",
    "hour_cos",
]

_HISTORY_COLUMNS = ["ts", "soil_moisture", "temperature", "humidity", "lux", "flow_rate"]


def _clamp(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


class SoilForecasterBaseline(SoilMoistureForecaster):
    """GBR-per-horizon baseline with a physics-decay cold-start fallback."""

    def predict(
        self,
        device_id: str,
        horizons_minutes: list[int],
        history: pd.DataFrame,
    ) -> ForecastResult:
        horizons = list(horizons_minutes)

        try:
            prepared = self._prepare_history(history)
        except Exception:
            prepared = pd.DataFrame(columns=_HISTORY_COLUMNS)

        valid_moisture = (
            prepared["soil_moisture"].dropna()
            if "soil_moisture" in prepared.columns
            else pd.Series(dtype=float)
        )
        if len(valid_moisture) < MIN_TRAIN_SAMPLES:
            return self._physics_fallback(horizons, prepared)

        try:
            feat_df = self._build_feature_frame(prepared)
            current_row = feat_df.iloc[[-1]][FEATURE_COLUMNS]
        except Exception:
            return self._physics_fallback(horizons, prepared)

        points: list[ForecastPoint] = []
        importance_sums: dict[str, float] = {}
        importance_fits = 0
        any_gbr_used = False

        for horizon in horizons:
            point: ForecastPoint | None = None
            try:
                X, y = self._build_training_set(feat_df, prepared, horizon)
                if len(X) < MIN_HORIZON_TRAIN_SAMPLES:
                    raise ValueError(
                        f"insufficient training samples for horizon={horizon}: {len(X)}"
                    )

                model = GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.05,
                    random_state=42,
                )
                model.fit(X.to_numpy(), y.to_numpy())

                raw_pred = float(model.predict(current_row.to_numpy())[0])
                predicted = _clamp(raw_pred, 0.0, 100.0)
                ci_margin = 3.0
                point = ForecastPoint(
                    horizon_minutes=horizon,
                    predicted_pct=predicted,
                    ci_low=_clamp(predicted - ci_margin, 0.0, 100.0),
                    ci_high=_clamp(predicted + ci_margin, 0.0, 100.0),
                )

                for name, importance in zip(FEATURE_COLUMNS, model.feature_importances_):
                    importance_sums[name] = importance_sums.get(name, 0.0) + float(importance)
                importance_fits += 1
                any_gbr_used = True
            except Exception:
                point = None

            if point is None:
                # Per-horizon fallback: this specific horizon couldn't be
                # fit (too few training rows, NaN in the current feature
                # vector, sklearn error, ...) but others may still succeed.
                fallback = self._physics_fallback([horizon], prepared)
                point = fallback.points[0]

            points.append(point)

        if not any_gbr_used:
            # Every horizon fell back -> treat the whole result as a
            # full cold start, per §4 of the doc.
            return self._physics_fallback(horizons, prepared)

        feature_importances = (
            {name: total / importance_fits for name, total in importance_sums.items()}
            if importance_fits
            else {}
        )

        return ForecastResult(
            points=points,
            model_version="gbr-0.1",
            is_cold_start=False,
            feature_importances=feature_importances,
        )

    # ------------------------------------------------------------------
    # History preparation
    # ------------------------------------------------------------------

    def _prepare_history(self, history: pd.DataFrame | None) -> pd.DataFrame:
        """Normalize `history` into the exact expected shape: all 6
        columns present, `ts` as sorted-ascending datetime, numeric columns
        coerced to float. Never raises -- unusable input becomes an empty
        frame with the right columns, which the cold-start gate in
        `predict()` will route straight to the physics fallback."""
        if history is None or len(history) == 0:
            return pd.DataFrame(columns=_HISTORY_COLUMNS)

        df = history.copy()
        for col in _HISTORY_COLUMNS:
            if col not in df.columns:
                df[col] = np.nan

        # `ts` may be pandas Timestamps already, or epoch seconds (float).
        if pd.api.types.is_numeric_dtype(df["ts"]):
            df["ts"] = pd.to_datetime(df["ts"], unit="s", errors="coerce")
        else:
            df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

        for col in ["soil_moisture", "temperature", "humidity", "lux", "flow_rate"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["ts"])
        df = df.sort_values("ts").reset_index(drop=True)
        return df[_HISTORY_COLUMNS]

    # ------------------------------------------------------------------
    # Feature engineering (GBR branch)
    # ------------------------------------------------------------------

    def _asof_lookup(self, df: pd.DataFrame, offset_minutes: float) -> np.ndarray:
        """For every row `i` in `df` (indexed 0..n-1, sorted by `ts`),
        find the `soil_moisture` value nearest to `ts_i + offset_minutes`
        within a +/-30s tolerance. Negative `offset_minutes` looks
        backward (lag features); positive looks forward (training labels).
        Rows with no match within tolerance get NaN."""
        n = len(df)
        if n == 0:
            return np.array([], dtype=float)

        source = (
            df[["ts", "soil_moisture"]]
            .dropna(subset=["ts", "soil_moisture"])
            .sort_values("ts")
        )
        if source.empty:
            return np.full(n, np.nan)

        left = df[["ts"]].copy()
        left["orig_idx"] = np.arange(n)
        left["lookup_ts"] = left["ts"] + pd.Timedelta(minutes=offset_minutes)
        left = left.sort_values("lookup_ts")

        merged = pd.merge_asof(
            left,
            source,
            left_on="lookup_ts",
            right_on="ts",
            direction="nearest",
            tolerance=pd.Timedelta(seconds=30),
            suffixes=("", "_match"),
        )
        merged = merged.sort_values("orig_idx")
        return merged["soil_moisture"].to_numpy()

    def _build_feature_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build the feature matrix (one row per history sample), columns
        exactly `FEATURE_COLUMNS`. `df` must already be `_prepare_history`
        output (sorted, reset index)."""
        working = df.reset_index(drop=True)
        feat = pd.DataFrame(index=working.index)

        feat["lag_1"] = self._asof_lookup(working, -1)
        feat["lag_5"] = self._asof_lookup(working, -5)
        feat["lag_15"] = self._asof_lookup(working, -15)
        feat["lag_30"] = self._asof_lookup(working, -30)
        feat["trend"] = working["soil_moisture"].to_numpy() - feat["lag_15"].to_numpy()

        feat["temp_now"] = working["temperature"].to_numpy()
        feat["humidity_now"] = working["humidity"].to_numpy()
        feat["lux_now"] = working["lux"].to_numpy()

        indexed = working.set_index("ts")
        rolling_mean = indexed[["temperature", "humidity", "lux"]].rolling("15min").mean()
        feat["temp_15m_avg"] = rolling_mean["temperature"].to_numpy()
        feat["humidity_15m_avg"] = rolling_mean["humidity"].to_numpy()
        feat["lux_15m_avg"] = rolling_mean["lux"].to_numpy()

        feat["flow_30m_cum"] = indexed["flow_rate"].rolling("30min").sum().to_numpy()

        hour_frac = working["ts"].dt.hour + working["ts"].dt.minute / 60.0
        feat["hour_sin"] = np.sin(2 * np.pi * hour_frac / 24.0).to_numpy()
        feat["hour_cos"] = np.cos(2 * np.pi * hour_frac / 24.0).to_numpy()

        return feat[FEATURE_COLUMNS]

    def _build_training_set(
        self, feat_df: pd.DataFrame, raw_df: pd.DataFrame, horizon_minutes: int
    ) -> tuple[pd.DataFrame, pd.Series]:
        """(X, y) for one horizon: X is `feat_df` (shared across all
        horizons), y is `soil_moisture` at `t_i + horizon_minutes` per row
        (via `_asof_lookup`). Rows missing any feature or label are
        dropped."""
        labels = self._asof_lookup(raw_df, horizon_minutes)
        working = feat_df[FEATURE_COLUMNS].copy()
        working["__label__"] = labels
        working = working.dropna()
        y = working.pop("__label__")
        return working, y

    # ------------------------------------------------------------------
    # Physics fallback (cold start / any GBR failure)
    # ------------------------------------------------------------------

    def _physics_fallback(
        self, horizons_minutes: list[int], history: pd.DataFrame | None
    ) -> ForecastResult:
        """Self-contained linear evaporation-decay proxy — NOT Hargreaves,
        NOT `WaterDemandEstimator`. `decay_rate_pct_per_day` scales the
        3%/day reference decay by how far current temp/lux are from the
        25 C / 50,000 lux reference condition."""
        current_moisture = DEFAULT_MOISTURE_PCT
        temp_now = DEFAULT_TEMP_C
        lux_now = DEFAULT_LUX

        try:
            if history is not None and len(history) > 0:
                if "soil_moisture" in history.columns:
                    series = history["soil_moisture"].dropna()
                    if len(series) > 0:
                        current_moisture = float(series.iloc[-1])
                if "temperature" in history.columns:
                    series = history["temperature"].dropna()
                    if len(series) > 0:
                        temp_now = float(series.iloc[-1])
                if "lux" in history.columns:
                    series = history["lux"].dropna()
                    if len(series) > 0:
                        lux_now = float(series.iloc[-1])
        except Exception:
            pass

        decay_rate_pct_per_day = (
            _REFERENCE_DECAY_PCT_PER_DAY
            * (temp_now / _REFERENCE_TEMP_C)
            * (lux_now / _REFERENCE_LUX)
        )

        points: list[ForecastPoint] = []
        for horizon in horizons_minutes:
            predicted = _clamp(
                current_moisture - decay_rate_pct_per_day * (horizon / 1440.0), 0.0, 100.0
            )
            ci_margin = 3.0 + 0.05 * horizon
            points.append(
                ForecastPoint(
                    horizon_minutes=horizon,
                    predicted_pct=predicted,
                    ci_low=_clamp(predicted - ci_margin, 0.0, 100.0),
                    ci_high=_clamp(predicted + ci_margin, 0.0, 100.0),
                )
            )

        return ForecastResult(
            points=points,
            model_version="physics-fallback",
            is_cold_start=True,
            feature_importances={},
        )

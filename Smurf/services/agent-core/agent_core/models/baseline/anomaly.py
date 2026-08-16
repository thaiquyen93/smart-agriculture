"""Baseline `AnomalyDetector` (docs/agent-core/05-ml-interfaces.md §3.4).

Two-part baseline:

Part A — multivariate Isolation Forest (`sklearn`) over the ~6h sliding
window of `topic_p` aggregates across all 6 devices (one row per
timestamp). Genuinely learned/statistical: flags points that are unusual
across the whole feature vector, and reports which features drove the
flag by comparing each feature to its column median.

Part B — 3 cross-device consistency rules (pipe-break/sensor-fault,
tank-leak, weather-sensor-fault). These are *rule-based on purpose* — a
single-device statistical model can't see "pump running but soil not
getting wetter", only a cross-device check can — and are labeled
`model_version="cross-device-rules-v1"`, distinct from the Isolation
Forest's `"isoforest-0.1"`, so a human/UI can always tell which kind of
evidence produced a given Anomaly. See docs §3.4, last paragraph: this is
a deliberate, disclosed simplification, not a pretense that everything
here is ML.

Column contract for `windows` (one row per topic_p timestamp, sorted
ascending by `ts`; `ts` may be a pandas Timestamp or epoch seconds —
`pd.to_datetime` handles both):
    ts,
    soil_moisture_avg, soil_moisture_trend,
    soil_temperature_avg, soil_temperature_trend,        # SOIL_01.temperature
    weather_temperature_avg, weather_temperature_trend,  # WEATHER_01.temperature
    humidity_avg, humidity_trend,
    flow_rate_avg, flow_rate_trend,
    power_avg, power_trend,
    ph_avg, ph_trend,
    level_avg, level_trend,
    lux_avg, lux_trend

Every column beyond `ts` is optional in practice: missing/NaN-heavy input
degrades gracefully (Part A is skipped if too few feature columns or rows
are present; a Part B rule is skipped if the columns it needs aren't
there) rather than raising. Per docs §4 "Chống cold-start": `detect()`
never lets a model exception crash the caller's session.
"""
from __future__ import annotations

import logging

import pandas as pd
from sklearn.ensemble import IsolationForest

from agent_core.models.base import Anomaly, AnomalyDetector

logger = logging.getLogger(__name__)

ISOFOREST_MODEL_VERSION = "isoforest-0.1"
RULES_MODEL_VERSION = "cross-device-rules-v1"

FEATURE_COLS = [
    "soil_moisture_avg", "soil_moisture_trend",
    "soil_temperature_avg", "soil_temperature_trend",
    "weather_temperature_avg", "weather_temperature_trend",
    "humidity_avg", "humidity_trend",
    "flow_rate_avg", "flow_rate_trend",
    "power_avg", "power_trend",
    "ph_avg", "ph_trend",
    "level_avg", "level_trend",
    "lux_avg", "lux_trend",
]

# --- Part A: Isolation Forest ------------------------------------------------
ISOFOREST_CONTAMINATION = 0.02
MIN_ROWS_FOR_ISOFOREST = 10
MIN_FEATURE_COLS_FOR_ISOFOREST = len(FEATURE_COLS) // 2  # 9 of 18 -> "thiếu quá nhiều cột" bail-out
TOP_N_CONTRIBUTING_FEATURES = 3

# --- Part B: cross-device consistency rules (docs §3.4, deliberately rule-based) ---
MIN_SUSTAINED_MINUTES = 10
SOIL_INCREASE_EPS = 0.1  # %, below this a soil-moisture change counts as "not rising"
FLOW_ZERO_EPS = 0.1  # L/min, below this the pump counts as "not running"
TANK_LEVEL_DROP_EPS = 0.5  # %, at/above this a level drop counts as "significant"
LUX_HIGH_PERCENTILE = 0.7
TEMP_DROP_THRESHOLD_C = 2.0  # degC, between two consecutive points


def _to_datetime_series(ts: pd.Series) -> pd.Series:
    """`ts` may already be pandas Timestamps, or raw epoch seconds (int/float)."""
    if pd.api.types.is_numeric_dtype(ts):
        return pd.to_datetime(ts, unit="s")
    return pd.to_datetime(ts)


def _as_py_datetime(value):
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


class AnomalyDetectorBaseline(AnomalyDetector):
    """Isolation Forest (Part A) + 3 cross-device rules (Part B). See module
    docstring and docs/agent-core/05-ml-interfaces.md §3.4 for the
    algorithm this implements."""

    def detect(self, zone: str, windows: pd.DataFrame) -> list[Anomaly]:
        if windows is None or len(windows) == 0 or "ts" not in windows.columns:
            return []

        try:
            df = windows.copy()
            df["_ts"] = _to_datetime_series(df["ts"])
            df = df.sort_values("_ts").reset_index(drop=True)
        except Exception:  # noqa: BLE001 - malformed ts must not crash the caller
            logger.exception("AnomalyDetectorBaseline.detect: failed to parse/sort ts for zone=%s", zone)
            return []

        anomalies: list[Anomaly] = []
        anomalies.extend(self._detect_multivariate(zone, df))
        anomalies.extend(self._detect_cross_device_rules(df))
        anomalies.sort(key=lambda a: a.detected_at)
        return anomalies

    # -- Part A ----------------------------------------------------------

    def _detect_multivariate(self, zone: str, df: pd.DataFrame) -> list[Anomaly]:
        try:
            present_cols = [c for c in FEATURE_COLS if c in df.columns]
            if len(df) < MIN_ROWS_FOR_ISOFOREST or len(present_cols) < MIN_FEATURE_COLS_FOR_ISOFOREST:
                return []

            X = df[present_cols].copy()
            X = X.fillna(X.median())
            X = X.fillna(0.0)  # columns that were entirely NaN -> their median is also NaN

            model = IsolationForest(contamination=ISOFOREST_CONTAMINATION, random_state=42)
            model.fit(X)
            raw_scores = -model.decision_function(X)
            score_range = raw_scores.max() - raw_scores.min()
            score_0_1 = (raw_scores - raw_scores.min()) / (score_range + 1e-9)
            predictions = model.predict(X)

            medians = X.median()
            results: list[Anomaly] = []
            for i in range(len(df)):
                if predictions[i] != -1:
                    continue
                diffs = (X.iloc[i] - medians).abs().sort_values(ascending=False)
                contributing = list(diffs.index[:TOP_N_CONTRIBUTING_FEATURES])
                results.append(
                    Anomaly(
                        anomaly_type="MULTIVARIATE_OUTLIER",
                        device_id=zone,
                        score_0_1=float(score_0_1[i]),
                        detected_at=_as_py_datetime(df["_ts"].iloc[i]),
                        model_version=ISOFOREST_MODEL_VERSION,
                        contributing_features=contributing,
                    )
                )
            return results
        except Exception:  # noqa: BLE001 - degrade to "no multivariate signal", Part B still runs
            logger.exception("AnomalyDetectorBaseline: Isolation Forest failed, skipping Part A")
            return []

    # -- Part B ------------------------------------------------------------

    def _detect_cross_device_rules(self, df: pd.DataFrame) -> list[Anomaly]:
        results: list[Anomaly] = []
        for rule in (
            self._rule_pipe_break_or_sensor_fault,
            self._rule_tank_leak,
            self._rule_weather_sensor_fault,
        ):
            try:
                results.extend(rule(df))
            except Exception:  # noqa: BLE001 - one bad rule must not block the others
                logger.exception("AnomalyDetectorBaseline: cross-device rule %s failed", rule.__name__)
        return results

    def _rule_pipe_break_or_sensor_fault(self, df: pd.DataFrame) -> list[Anomaly]:
        """PUMP_01.flow_rate sustained > 0 for >= MIN_SUSTAINED_MINUTES but
        SOIL_01.soil_moisture doesn't rise -> suspected pipe break or dead
        soil sensor. Checked once at the end of each contiguous sustained-flow
        segment (not once per row inside it), to avoid duplicate emits for one
        continuous event."""
        if "flow_rate_avg" not in df.columns or "soil_moisture_avg" not in df.columns:
            return []

        results: list[Anomaly] = []
        flowing = df["flow_rate_avg"] > FLOW_ZERO_EPS
        n = len(df)
        i = 0
        while i < n:
            if not bool(flowing.iloc[i]):
                i += 1
                continue
            start = i
            j = i
            while j + 1 < n and bool(flowing.iloc[j + 1]):
                j += 1

            ts_start = df["_ts"].iloc[start]
            ts_end = df["_ts"].iloc[j]
            duration_minutes = (ts_end - ts_start).total_seconds() / 60.0
            if duration_minutes >= MIN_SUSTAINED_MINUTES:
                soil_start = df["soil_moisture_avg"].iloc[start]
                soil_end = df["soil_moisture_avg"].iloc[j]
                if pd.notna(soil_start) and pd.notna(soil_end) and (soil_end - soil_start) <= SOIL_INCREASE_EPS:
                    results.append(
                        Anomaly(
                            anomaly_type="SUSPECTED_PIPE_BREAK_OR_SENSOR_FAULT",
                            device_id="SOIL_01",
                            score_0_1=0.9,
                            detected_at=_as_py_datetime(ts_end),
                            model_version=RULES_MODEL_VERSION,
                            contributing_features=["flow_rate_avg", "soil_moisture_avg"],
                        )
                    )
            i = j + 1
        return results

    def _rule_tank_leak(self, df: pd.DataFrame) -> list[Anomaly]:
        """TANK_01.level drops sharply between two consecutive points while
        PUMP_01.flow_rate is ~0 at the later point -> suspected leak (a real
        drawdown from irrigation would show flow > 0)."""
        if "level_avg" not in df.columns or "flow_rate_avg" not in df.columns:
            return []

        results: list[Anomaly] = []
        n = len(df)
        for i in range(n - 1):
            level_i = df["level_avg"].iloc[i]
            level_j = df["level_avg"].iloc[i + 1]
            flow_j = df["flow_rate_avg"].iloc[i + 1]
            if pd.isna(level_i) or pd.isna(level_j) or pd.isna(flow_j):
                continue
            if (level_i - level_j) >= TANK_LEVEL_DROP_EPS and flow_j <= FLOW_ZERO_EPS:
                results.append(
                    Anomaly(
                        anomaly_type="SUSPECTED_TANK_LEAK",
                        device_id="TANK_01",
                        score_0_1=0.9,
                        detected_at=_as_py_datetime(df["_ts"].iloc[i + 1]),
                        model_version=RULES_MODEL_VERSION,
                        contributing_features=["level_avg", "flow_rate_avg"],
                    )
                )
        return results

    def _rule_weather_sensor_fault(self, df: pd.DataFrame) -> list[Anomaly]:
        """SUN_01.lux is high (top LUX_HIGH_PERCENTILE of the batch) while
        WEATHER_01.temperature drops sharply between two consecutive points
        -> physically inconsistent (bright sun + sudden cold), suspected
        weather sensor fault."""
        if "lux_avg" not in df.columns or "weather_temperature_avg" not in df.columns:
            return []
        if df["lux_avg"].dropna().empty:
            return []

        lux_threshold = df["lux_avg"].quantile(LUX_HIGH_PERCENTILE)
        results: list[Anomaly] = []
        n = len(df)
        for i in range(n - 1):
            lux_j = df["lux_avg"].iloc[i + 1]
            temp_i = df["weather_temperature_avg"].iloc[i]
            temp_j = df["weather_temperature_avg"].iloc[i + 1]
            if pd.isna(lux_j) or pd.isna(temp_i) or pd.isna(temp_j):
                continue
            if lux_j >= lux_threshold and (temp_i - temp_j) >= TEMP_DROP_THRESHOLD_C:
                results.append(
                    Anomaly(
                        anomaly_type="SUSPECTED_WEATHER_SENSOR_FAULT",
                        device_id="WEATHER_01",
                        score_0_1=0.85,
                        detected_at=_as_py_datetime(df["_ts"].iloc[i + 1]),
                        model_version=RULES_MODEL_VERSION,
                        contributing_features=["lux_avg", "weather_temperature_avg"],
                    )
                )
        return results

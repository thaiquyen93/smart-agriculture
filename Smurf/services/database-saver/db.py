import sqlite3
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("db_manager")
DB_PATH = Path(__file__).parent / "data" / "smurf_database.sqlite"

class DatabaseManager:
    """
    SQLite Database Manager.
    Persists historical raw telemetry, aggregated windows, alerts, and AI decision logs.
    """
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = DB_PATH
        self._init_tables()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_aggregated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    window_type TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    anomalies TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id TEXT NOT NULL,
                    weather_condition TEXT,
                    risk_score REAL,
                    risk_level TEXT,
                    synoptic_analysis TEXT,
                    decisions TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()
            logger.info(f"✓ SQLite Database initialized at {self.db_path}")

    def save_raw(self, device_id: str, payload: dict):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO telemetry_raw (device_id, payload, created_at) VALUES (?, ?, ?)",
                    (device_id, json.dumps(payload), time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving raw telemetry to DB: {e}")

    def save_aggregated(self, device_id: str, agg: dict):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO telemetry_aggregated (device_id, window_type, metrics, anomalies, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        device_id,
                        agg.get("window_type", "UNKNOWN"),
                        json.dumps(agg.get("metrics", {})),
                        json.dumps(agg.get("anomalies", [])),
                        time.time()
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving aggregated window to DB: {e}")

    def save_forecast(self, station_id: str, forecast: dict):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO ai_forecasts 
                       (station_id, weather_condition, risk_score, risk_level, synoptic_analysis, decisions, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        station_id,
                        forecast.get("weather_condition"),
                        forecast.get("risk_score", 0.0),
                        forecast.get("risk_level", "LOW"),
                        forecast.get("synoptic_analysis", ""),
                        json.dumps(forecast.get("smart_operational_decisions", [])),
                        time.time()
                    )
                )
                conn.commit()
                logger.info(f"💾 [SAVED TO DB] AI Decision Forecast for station {station_id}")
        except Exception as e:
            logger.error(f"Error saving forecast to DB: {e}")

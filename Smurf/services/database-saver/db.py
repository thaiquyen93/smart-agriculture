import sqlite3
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("db_manager")
DB_PATH = Path(__file__).parent / "data" / "smurf_database.sqlite"

class DatabaseManager:
    """
    SQLite Enterprise Database Manager for Track B: Smart Agriculture.
    Persists:
      - telemetry_raw (Tagged by device_id & topic_name for topic-based queries)
      - telemetry_aggregated (Windowed metrics & anomalies)
      - irrigation_plans (Created by Irrigation Planning Agent)
      - inspection_tasks (Field maintenance tickets created by Farm Action Agent)
      - agent_logs (Multi-Agent Reasoning Trace & Verification evidence)
      - ai_forecasts (Synoptic risk assessment & operational decisions)
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
            # 1. Telemetry Raw Data Table (Tagged by Device ID & Topic Name)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    topic_name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_device ON telemetry_raw(device_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_topic ON telemetry_raw(topic_name)")

            # 2. Telemetry Aggregated Windows Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_aggregated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    topic_name TEXT NOT NULL,
                    window_type TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    anomalies TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agg_device ON telemetry_aggregated(device_id)")

            # 3. Irrigation Plans Table (Created by Irrigation Planning Agent)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS irrigation_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id TEXT UNIQUE NOT NULL,
                    area_id TEXT NOT NULL,
                    target_moisture REAL NOT NULL,
                    water_amount_liters REAL NOT NULL,
                    priority TEXT NOT NULL,
                    suggested_time TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
                    reasoning_summary TEXT,
                    created_at REAL NOT NULL
                )
            """)

            # 4. Inspection Tasks Table (Created by Farm Action Agent for Offline/Faulty Devices)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inspection_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    device_id TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    assigned_to TEXT DEFAULT 'Field Engineer',
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
                    created_at REAL NOT NULL
                )
            """)

            # 5. Multi-Agent Logs & Reasoning Trace Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    input_prompt TEXT,
                    output_response TEXT,
                    evidence_data TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_session ON agent_logs(session_id)")

            # 6. AI Decision & Synoptic Risk Table
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
            logger.info(f"✓ SQLite Database initialized with Track B Schema at {self.db_path}")

    # =========================================================================
    # WRITE OPERATIONS
    # =========================================================================

    def save_raw(self, device_id: str, payload: dict, topic_name: str = "topic_raw"):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO telemetry_raw (device_id, topic_name, payload, created_at) VALUES (?, ?, ?, ?)",
                    (device_id, topic_name, json.dumps(payload), time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving raw telemetry ({device_id}): {e}")

    def save_aggregated(self, device_id: str, agg: dict, topic_name: str = "topic_p"):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO telemetry_aggregated (device_id, topic_name, window_type, metrics, anomalies, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        device_id,
                        topic_name,
                        agg.get("window_type", "UNKNOWN"),
                        json.dumps(agg.get("metrics", {})),
                        json.dumps(agg.get("anomalies", [])),
                        time.time()
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving aggregated window ({device_id}): {e}")

    def save_irrigation_plan(self, plan: dict) -> str:
        plan_id = plan.get("plan_id") or f"PLAN-{int(time.time()*1000)}"
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO irrigation_plans 
                       (plan_id, area_id, target_moisture, water_amount_liters, priority, suggested_time, status, reasoning_summary, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plan_id,
                        plan.get("area_id", "Khu A"),
                        plan.get("target_moisture", 60.0),
                        plan.get("water_amount_liters", 500.0),
                        plan.get("priority", "MEDIUM"),
                        plan.get("suggested_time", "Immediate"),
                        plan.get("status", "PENDING_APPROVAL"),
                        plan.get("reasoning_summary", ""),
                        time.time()
                    )
                )
                conn.commit()
                logger.info(f"💾 [SAVED PLAN] Irrigation Plan {plan_id} created.")
        except Exception as e:
            logger.error(f"Error saving irrigation plan: {e}")
        return plan_id

    def update_irrigation_plan_status(self, plan_id: str, status: str):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE irrigation_plans SET status = ? WHERE plan_id = ?",
                    (status, plan_id)
                )
                conn.commit()
                logger.info(f"💾 [UPDATE PLAN] Plan {plan_id} -> {status}")
        except Exception as e:
            logger.error(f"Error updating plan status: {e}")

    def save_inspection_task(self, task: dict) -> str:
        task_id = task.get("task_id") or f"TASK-{int(time.time()*1000)}"
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO inspection_tasks 
                       (task_id, device_id, issue_type, severity, description, assigned_to, status, verification_status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        task.get("device_id", "DEV_UNKNOWN"),
                        task.get("issue_type", "MAINTENANCE"),
                        task.get("severity", "WARNING"),
                        task.get("description", "Routine inspection"),
                        task.get("assigned_to", "Field Engineer"),
                        task.get("status", "OPEN"),
                        task.get("verification_status", "VERIFIED"),
                        time.time()
                    )
                )
                conn.commit()
                logger.info(f"💾 [SAVED TASK] Inspection Task {task_id} created.")
        except Exception as e:
            logger.error(f"Error saving inspection task: {e}")
        return task_id

    def save_agent_log(self, session_id: str, agent_name: str, action_type: str, 
                       output_response: str, input_prompt: str = "", evidence_data: dict = None):
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO agent_logs 
                       (session_id, agent_name, action_type, input_prompt, output_response, evidence_data, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        agent_name,
                        action_type,
                        input_prompt,
                        output_response,
                        json.dumps(evidence_data or {}),
                        time.time()
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving agent log: {e}")

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

    # =========================================================================
    # READ / QUERY OPERATIONS
    # =========================================================================

    def get_latest_telemetry(self, device_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if device_id:
                cur = conn.execute(
                    "SELECT * FROM telemetry_raw WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                    (device_id, limit)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM telemetry_raw ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["payload"] = json.loads(item["payload"])
                results.append(item)
            return results

    def get_latest_device_states(self) -> Dict[str, Dict[str, Any]]:
        """Returns the most recent payload for each of the 6 devices."""
        devices = ["SOIL_01", "WEATHER_01", "PUMP_01", "PH_01", "TANK_01", "SUN_01"]
        states = {}
        with self._get_conn() as conn:
            for dev in devices:
                cur = conn.execute(
                    "SELECT * FROM telemetry_raw WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                    (dev,)
                )
                row = cur.fetchone()
                if row:
                    item = dict(row)
                    item["payload"] = json.loads(item["payload"])
                    states[dev] = item
        return states

    def get_irrigation_plans(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM irrigation_plans ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_inspection_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT * FROM inspection_tasks ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_agent_logs(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if session_id:
                cur = conn.execute(
                    "SELECT * FROM agent_logs WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                    (session_id, limit)
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("evidence_data"):
                    item["evidence_data"] = json.loads(item["evidence_data"])
                results.append(item)
            return results

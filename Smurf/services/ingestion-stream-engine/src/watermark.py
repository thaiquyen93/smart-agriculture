import time
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger("watermark_engine")

class WatermarkManager:
    """
    Bounded-Out-Of-Orderness Watermarking Implementation for Real-Time IoT Telemetry.
    Tracks observed event times and emits watermarks advancing with:
    Watermark = max(event_time_observed) - max_out_of_orderness_sec
    """
    def __init__(self, max_out_of_orderness_sec: float = 5.0):
        self.max_out_of_orderness = max_out_of_orderness_sec
        self.max_event_time = 0.0
        self.current_watermark = 0.0
        self.total_events = 0
        self.late_events_count = 0
        self.on_time_events_count = 0

    def process_event(self, record: Dict[str, Any]) -> Tuple[bool, float, float]:
        """
        Processes an incoming record based on its event_time.
        Returns:
            (is_on_time: bool, event_time: float, current_watermark: float)
        """
        self.total_events += 1
        event_time = float(record.get("event_time", time.time()))

        if event_time > self.max_event_time:
            self.max_event_time = event_time
            self.current_watermark = max(0.0, self.max_event_time - self.max_out_of_orderness)

        # Check if record is late (arrived after watermark has passed its event_time)
        if event_time < self.current_watermark:
            self.late_events_count += 1
            is_on_time = False
            lateness = self.current_watermark - event_time
            logger.debug(f"[LATE EVENT] Station {record.get('station_id')} lateness: {lateness:.2f}s < Watermark: {self.current_watermark:.2f}")
        else:
            self.on_time_events_count += 1
            is_on_time = True

        return is_on_time, event_time, self.current_watermark

    def get_stats(self) -> Dict[str, Any]:
        return {
            "max_event_time": self.max_event_time,
            "current_watermark": self.current_watermark,
            "max_out_of_orderness_sec": self.max_out_of_orderness,
            "total_events": self.total_events,
            "on_time_events": self.on_time_events_count,
            "late_events": self.late_events_count,
            "late_percentage": round((self.late_events_count / max(1, self.total_events)) * 100, 2)
        }

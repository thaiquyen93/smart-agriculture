import logging
import math
from typing import Dict, List, Any
from src.aggregators import aggregate_window_records

logger = logging.getLogger("window_manager")

class WindowManager:
    """
    Stateful Window Manager supporting:
    - Tumbling Window (1 minute) -> topic_p
    - Sliding Window (5 minutes, slide 1 minute) -> topic_p
    - Hourly Window (1 hour) -> topic_h
    governed by Event-Time Watermarks.
    """
    def __init__(self, tumbling_size_sec: int = 60, sliding_size_sec: int = 300, sliding_step_sec: int = 60, hourly_size_sec: int = 3600):
        self.tumbling_size_sec = tumbling_size_sec
        self.sliding_size_sec = sliding_size_sec
        self.sliding_step_sec = sliding_step_sec
        self.hourly_size_sec = hourly_size_sec

        # State storage: {station_id: {window_id: [records]}}
        self.tumbling_windows: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        self.hourly_windows: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}
        
        # Sliding buffer of raw records: {station_id: [records]}
        self.sliding_buffers: Dict[str, List[Dict[str, Any]]] = {}
        self.last_slide_time: Dict[str, float] = {}

    def assign_tumbling_window(self, station_id: str, record: Dict[str, Any], event_time: float):
        if station_id not in self.tumbling_windows:
            self.tumbling_windows[station_id] = {}

        window_idx = int(event_time // self.tumbling_size_sec)
        if window_idx not in self.tumbling_windows[station_id]:
            self.tumbling_windows[station_id][window_idx] = []
        self.tumbling_windows[station_id][window_idx].append(record)

    def assign_sliding_window(self, station_id: str, record: Dict[str, Any], event_time: float):
        if station_id not in self.sliding_buffers:
            self.sliding_buffers[station_id] = []
            self.last_slide_time[station_id] = event_time

        self.sliding_buffers[station_id].append(record)

    def assign_hourly_window(self, station_id: str, record: Dict[str, Any], event_time: float):
        if station_id not in self.hourly_windows:
            self.hourly_windows[station_id] = {}

        window_idx = int(event_time // self.hourly_size_sec)
        if window_idx not in self.hourly_windows[station_id]:
            self.hourly_windows[station_id][window_idx] = []
        self.hourly_windows[station_id][window_idx].append(record)

    def advance_watermark_and_trigger(self, current_watermark: float) -> List[Dict[str, Any]]:
        """
        Closes all windows where window_end <= current_watermark and emits aggregations.
        """
        emitted_aggregations = []

        # 1. Check Tumbling 1m Windows
        for station_id, windows in list(self.tumbling_windows.items()):
            closed_indices = []
            for win_idx, records in list(windows.items()):
                window_start = win_idx * self.tumbling_size_sec
                window_end = window_start + self.tumbling_size_sec

                if current_watermark >= window_end:
                    agg = aggregate_window_records(records, "TUMBLING_1M", window_start, window_end)
                    if agg:
                        emitted_aggregations.append(agg)
                    closed_indices.append(win_idx)

            for idx in closed_indices:
                del windows[idx]

        # 2. Check Sliding 5m Windows (Slide 1m)
        for station_id, buffer in list(self.sliding_buffers.items()):
            if not buffer:
                continue

            last_emitted = self.last_slide_time.get(station_id, 0.0)
            if current_watermark - last_emitted >= self.sliding_step_sec:
                window_end = current_watermark
                window_start = window_end - self.sliding_size_sec

                window_records = [r for r in buffer if window_start <= r.get("event_time", 0.0) <= window_end]
                
                if window_records:
                    agg = aggregate_window_records(window_records, "SLIDING_5M", window_start, window_end)
                    if agg:
                        emitted_aggregations.append(agg)

                self.last_slide_time[station_id] = current_watermark

                # Evict records older than sliding window size
                retention_cutoff = current_watermark - self.sliding_size_sec - 30.0
                self.sliding_buffers[station_id] = [r for r in buffer if r.get("event_time", 0.0) >= retention_cutoff]

        # 3. Check Hourly 1h Windows
        for station_id, windows in list(self.hourly_windows.items()):
            closed_indices = []
            for win_idx, records in list(windows.items()):
                window_start = win_idx * self.hourly_size_sec
                window_end = window_start + self.hourly_size_sec

                if current_watermark >= window_end:
                    agg = aggregate_window_records(records, "HOURLY_1H", window_start, window_end)
                    if agg:
                        emitted_aggregations.append(agg)
                    closed_indices.append(win_idx)

            for idx in closed_indices:
                del windows[idx]

        return emitted_aggregations

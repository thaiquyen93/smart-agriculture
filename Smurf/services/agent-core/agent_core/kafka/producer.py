"""Kafka Producer for agent-core output events.

Produces to 5 topics (03-contracts.md §2.2):
- topic_agent_events: real-time agent trace
- topic_plans: irrigation schedules
- topic_tasks: inspection tickets
- topic_notifications: alerts
- topic_verifications: verification results
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from kafka import KafkaProducer
from kafka.errors import KafkaError

from agent_core.config import Settings

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SEC = 5.0


def _json_serialize(obj: Any) -> bytes:
    """Serialize to JSON bytes."""
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class AgentEventProducer:
    """Kafka producer for agent-core output events.

    Thread-safe. Auto-reconnects on failure (never crashes the process).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._producer: KafkaProducer | None = None
        self._lock = threading.Lock()
        self._connected = False

    def connect(self) -> bool:
        """Establish connection to Kafka. Returns True if successful."""
        with self._lock:
            if self._producer is not None:
                return True

            try:
                self._producer = KafkaProducer(
                    bootstrap_servers=self.settings.kafka_bootstrap_servers.split(","),
                    value_serializer=_json_serialize,
                    acks=1,  # Wait for leader acknowledgment
                    retries=3,
                    max_in_flight_requests_per_connection=5,
                )
                self._connected = True
                logger.info("AgentEventProducer connected to Kafka (%s)", self.settings.kafka_bootstrap_servers)
                return True
            except KafkaError as exc:
                logger.warning("AgentEventProducer failed to connect: %s", exc)
                self._producer = None
                self._connected = False
                return False

    @property
    def is_connected(self) -> bool:
        """Check if producer is connected."""
        return self._connected

    def send_agent_event(self, event: dict) -> bool:
        """Send AgentEvent to topic_agent_events.

        Key: session_id (for partitioning — all events of one session go to same partition).
        Returns True if sent successfully.
        """
        return self._send(
            topic=self.settings.topic_agent_events,
            key=event.get("session_id", ""),
            value=event,
        )

    def send_plan(self, plan: dict) -> bool:
        """Send IrrigationSchedule to topic_plans.

        Key: schedule_id.
        """
        return self._send(
            topic=self.settings.topic_plans,
            key=plan.get("schedule_id", ""),
            value=plan,
        )

    def send_task(self, task: dict) -> bool:
        """Send InspectionTicket to topic_tasks.

        Key: ticket_id.
        """
        return self._send(
            topic=self.settings.topic_tasks,
            key=task.get("ticket_id", ""),
            value=task,
        )

    def send_notification(self, notification: dict) -> bool:
        """Send Notification to topic_notifications.

        Key: notification_id.
        """
        return self._send(
            topic=self.settings.topic_notifications,
            key=notification.get("notification_id", ""),
            value=notification,
        )

    def send_verification(self, verification: dict) -> bool:
        """Send VerificationResult to topic_verifications.

        Key: session_id (correlate with agent_events).
        """
        return self._send(
            topic=self.settings.topic_verifications,
            key=verification.get("session_id", ""),
            value=verification,
        )

    def _send(self, topic: str, key: str, value: dict) -> bool:
        """Internal send with auto-reconnect on failure."""
        if not self._connected:
            if not self.connect():
                logger.warning("Cannot send to %s: producer not connected", topic)
                return False

        try:
            with self._lock:
                if self._producer is None:
                    return False

                future = self._producer.send(
                    topic,
                    key=key.encode("utf-8") if key else None,
                    value=value,
                )
                # Wait for send to complete (with timeout)
                future.get(timeout=5)
                return True

        except KafkaError as exc:
            logger.error("Failed to send to %s: %s", topic, exc)
            self._connected = False
            self._producer = None
            return False
        except Exception as exc:
            logger.error("Unexpected error sending to %s: %s", topic, exc)
            return False

    def flush(self) -> None:
        """Flush pending messages (blocking)."""
        with self._lock:
            if self._producer is not None:
                try:
                    self._producer.flush(timeout=5)
                except Exception as exc:
                    logger.warning("Flush failed: %s", exc)

    def close(self) -> None:
        """Close producer connection."""
        with self._lock:
            if self._producer is not None:
                try:
                    self._producer.close(timeout=5)
                except Exception as exc:
                    logger.warning("Close failed: %s", exc)
                finally:
                    self._producer = None
                    self._connected = False

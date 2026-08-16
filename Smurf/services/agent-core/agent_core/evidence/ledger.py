"""Evidence Ledger (roadmap M1.3) — every number the Field IoT Agent's read
tools hand back to the LLM must be backed by a resolvable `evidence_id`
(ADR-003-evidence-refs-only.md). Shape matches EvidenceRecord in
docs/agent-core/03-contracts.md §3.2.

Scope decision for M1 (see plan): in-memory only. The persisted
`evidence_ledger` SQLite table in 04-integration-guide.md §4 is owned by
database-saver and written once a `SessionResult` exists — that's M2, when
the Router/Coordinator/Verifier roster exists. This ledger is the thing
those sessions will eventually read from.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass

from agent_core.devices import DeviceId, Freshness, WindowType


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    device_id: DeviceId
    metric: str
    value_text: str  # string, not number — see 03-contracts.md §3.2 note
    unit: str
    observed_at: float
    age_seconds: float
    freshness: Freshness
    source_topic: str
    window_type: WindowType
    is_absence_record: bool = False


class EvidenceLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, EvidenceRecord] = {}
        self._counter = itertools.count(1)

    def record(
        self,
        *,
        device_id: DeviceId,
        metric: str,
        value_text: str,
        unit: str,
        observed_at: float,
        age_seconds: float,
        freshness: Freshness,
        source_topic: str,
        window_type: WindowType = WindowType.NONE,
        is_absence_record: bool = False,
    ) -> EvidenceRecord:
        with self._lock:
            evidence_id = f"EV-{next(self._counter)}"
            rec = EvidenceRecord(
                evidence_id=evidence_id,
                device_id=device_id,
                metric=metric,
                value_text=value_text,
                unit=unit,
                observed_at=observed_at,
                age_seconds=age_seconds,
                freshness=freshness,
                source_topic=source_topic,
                window_type=window_type,
                is_absence_record=is_absence_record,
            )
            self._records[evidence_id] = rec
            return rec

    def resolve(self, evidence_id: str) -> EvidenceRecord | None:
        with self._lock:
            return self._records.get(evidence_id)

    def all(self) -> list[EvidenceRecord]:
        """Every record ever written, insertion order. Used by tests and by
        the Verifier's future `audit_evidence` tool (02-agents-and-tools.md
        C.6) — not needed for the 4 Field IoT read tools themselves."""
        with self._lock:
            return list(self._records.values())

from __future__ import annotations

from agent_core.devices import DeviceId, Freshness, WindowType
from agent_core.evidence.ledger import EvidenceLedger


def _record(ledger: EvidenceLedger, **overrides):
    defaults = dict(
        device_id=DeviceId.SOIL_01,
        metric="soil_moisture",
        value_text="31.4",
        unit="%",
        observed_at=1000.0,
        age_seconds=12.0,
        freshness=Freshness.FRESH,
        source_topic="topic_raw",
    )
    defaults.update(overrides)
    return ledger.record(**defaults)


def test_record_generates_ev_prefixed_id():
    ledger = EvidenceLedger()
    rec = _record(ledger)
    assert rec.evidence_id.startswith("EV-")


def test_ids_are_unique_and_increasing():
    ledger = EvidenceLedger()
    rec1 = _record(ledger)
    rec2 = _record(ledger)
    assert rec1.evidence_id != rec2.evidence_id


def test_resolve_returns_the_same_record():
    ledger = EvidenceLedger()
    rec = _record(ledger)
    resolved = ledger.resolve(rec.evidence_id)
    assert resolved == rec


def test_resolve_unknown_id_returns_none():
    ledger = EvidenceLedger()
    assert ledger.resolve("EV-999999") is None


def test_absence_record_round_trips():
    ledger = EvidenceLedger()
    rec = _record(
        ledger,
        value_text="—",
        freshness=Freshness.OFFLINE,
        is_absence_record=True,
        window_type=WindowType.NONE,
    )
    resolved = ledger.resolve(rec.evidence_id)
    assert resolved.is_absence_record is True
    assert resolved.value_text == "—"

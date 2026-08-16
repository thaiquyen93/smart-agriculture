"""Freshness classification + data_completeness — pure functions, no I/O.

Thresholds come from Settings (`FRESHNESS_FRESH_SEC=60`,
`FRESHNESS_STALE_SEC=600`, docs/agent-core/04-integration-guide.md §7):
  age_seconds <= fresh_sec        -> FRESH
  fresh_sec  < age_seconds <= stale_sec -> STALE
  age_seconds > stale_sec (or never seen) -> OFFLINE
"""
from __future__ import annotations

from agent_core.devices import Freshness

# Worst-wins ordering, shared by every caller that reduces several metric
# readings down to one device-level freshness (get_device_snapshot,
# get_freshness_report, GET /api/v1/state/farm).
RANK: dict[Freshness, int] = {Freshness.FRESH: 0, Freshness.STALE: 1, Freshness.OFFLINE: 2}


def worse(a: Freshness, b: Freshness) -> Freshness:
    return b if RANK[b] > RANK[a] else a


def classify(age_seconds: float | None, *, fresh_sec: int, stale_sec: int) -> Freshness:
    """`age_seconds=None` means the device has never sent a single reading
    — always OFFLINE, never a bare null (02-agents-and-tools.md A.2)."""
    if age_seconds is None:
        return Freshness.OFFLINE
    if age_seconds <= fresh_sec:
        return Freshness.FRESH
    if age_seconds <= stale_sec:
        return Freshness.STALE
    return Freshness.OFFLINE


def clamp_age(age_seconds: float | None) -> float | None:
    """Display-layer clamp, not a classification concern: `classify()`
    already treats a slightly-negative age as FRESH correctly. Negative
    ages do happen in practice — a message timestamped on the producer's
    host clock can arrive a few hundred ms "before" the container's own
    clock ticks that far (observed with Docker Desktop VM clock lag during
    M1 live verification) — and showing "-1 giây" to a user is just
    confusing, so clamp at the point of display, not at the point of
    measurement."""
    return None if age_seconds is None else max(0.0, age_seconds)


def data_completeness(freshness_by_device: dict[str, Freshness]) -> tuple[str, str]:
    """Returns (`"5/6"`, mode) where mode is `"FULL"` if every device is
    FRESH, else `"PARTIAL"`. STALE/OFFLINE devices both count as "not
    complete" — only FRESH counts, matching the `data_completeness` example
    in 03-contracts.md (`"5/6"` alongside `mode: "PARTIAL"`)."""
    total = len(freshness_by_device)
    fresh_count = sum(1 for f in freshness_by_device.values() if f == Freshness.FRESH)
    ratio = f"{fresh_count}/{total}" if total else "0/0"
    mode = "FULL" if total and fresh_count == total else "PARTIAL"
    return ratio, mode

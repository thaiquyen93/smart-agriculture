"""Boundary tests for agent_core.state.freshness — the exact 60s/600s edges
matter (roadmap M1.2 exit criterion: offline transition after 10 minutes)."""
from __future__ import annotations

from agent_core.devices import Freshness
from agent_core.state.freshness import classify, data_completeness

FRESH_SEC = 60
STALE_SEC = 600


def _classify(age):
    return classify(age, fresh_sec=FRESH_SEC, stale_sec=STALE_SEC)


def test_never_seen_is_offline():
    assert _classify(None) == Freshness.OFFLINE


def test_zero_age_is_fresh():
    assert _classify(0) == Freshness.FRESH


def test_exactly_at_fresh_boundary_is_fresh():
    assert _classify(60) == Freshness.FRESH


def test_just_past_fresh_boundary_is_stale():
    assert _classify(61) == Freshness.STALE


def test_exactly_at_stale_boundary_is_stale():
    assert _classify(600) == Freshness.STALE


def test_just_past_stale_boundary_is_offline():
    assert _classify(601) == Freshness.OFFLINE


def test_far_past_is_offline():
    assert _classify(999_999) == Freshness.OFFLINE


def test_data_completeness_all_fresh_is_full():
    ratio, mode = data_completeness({"A": Freshness.FRESH, "B": Freshness.FRESH})
    assert ratio == "2/2"
    assert mode == "FULL"


def test_data_completeness_partial():
    ratio, mode = data_completeness(
        {"A": Freshness.FRESH, "B": Freshness.STALE, "C": Freshness.OFFLINE}
    )
    assert ratio == "1/3"
    assert mode == "PARTIAL"


def test_data_completeness_stale_does_not_count_as_fresh():
    ratio, mode = data_completeness({"A": Freshness.STALE})
    assert ratio == "0/1"
    assert mode == "PARTIAL"


def test_data_completeness_empty():
    ratio, mode = data_completeness({})
    assert ratio == "0/0"
    assert mode == "PARTIAL"

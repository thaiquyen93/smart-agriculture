"""Verification data models.

Follows docs/agent-core/03-contracts.md §3.6.
Verifier must read_back from store/DB, not RAM (ADR Rule 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VerificationStatus(str, Enum):
    """Verdict from Verifier (03-contracts.md §3.6)."""
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    MISMATCH = "MISMATCH"
    ESCALATED = "ESCALATED"


@dataclass
class FieldDifference:
    """One field mismatch between intent and read-back."""
    field: str
    intended: str
    actual: str


@dataclass
class EvidenceAudit:
    """Audit trail of evidence used in decisions (ADR-003 enforcement).

    Checks:
    - All decisions have evidence_refs
    - Evidence exists in ledger
    - Evidence freshness (STALE/OFFLINE evidence → confidence=TENTATIVE)
    - No unsourced_numbers (LLM fabricating numbers without evidence)
    """
    decisions_total: int
    decisions_without_evidence: int
    stale_evidence_used: list[str] = field(default_factory=list)
    offline_evidence_used: list[str] = field(default_factory=list)
    unsourced_numbers: list[str] = field(default_factory=list)

    def is_clean(self) -> bool:
        """True if no violations found."""
        return (
            self.decisions_without_evidence == 0
            and len(self.stale_evidence_used) == 0
            and len(self.offline_evidence_used) == 0
            and len(self.unsourced_numbers) == 0
        )


@dataclass
class VerificationResult:
    """Result from Verifier.verify() (03-contracts.md §3.6).

    Proof of real verification: read_back_ok proves we hit persistence layer.
    Test acceptance: delete record from DB → rerun → must show MISMATCH.
    """
    verification_id: str
    session_id: str
    object_type: str  # "IRRIGATION_SCHEDULE" | "INSPECTION_TICKET"
    object_id: str
    verdict: VerificationStatus
    read_back_ok: bool
    field_matches: int
    field_mismatches: int
    differences: list[FieldDifference] = field(default_factory=list)
    evidence_audit: EvidenceAudit = field(default_factory=lambda: EvidenceAudit(0, 0))
    retry_count: int = 0
    message_vi: str = ""
    verified_at_iso: str = ""

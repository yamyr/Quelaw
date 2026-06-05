"""Shared data types and the controlled vocabulary for statuses.

The wording of statuses is a hard requirement from the spec: never assert that a
case is "fake" or "good law". We only ever say it is or isn't *in the dataset*,
or that it needs manual review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

# --- Citation types -------------------------------------------------------
CASE = "case"
STATUTE = "statute"
RULE = "rule"
UNKNOWN = "unknown"

# --- Verification statuses ------------------------------------------------
VERIFIED = "verified"
NOT_FOUND = "not_found_in_dataset"
UNCERTAIN = "uncertain_match"
REQUIRES_REVIEW = "requires_manual_review"

STATUS_LABEL = {
    VERIFIED: "Verified in dataset",
    NOT_FOUND: "Not found in dataset",
    UNCERTAIN: "Uncertain match",
    REQUIRES_REVIEW: "Requires manual review",
}

# Emoji/colour hints for the UI.
STATUS_ICON = {
    VERIFIED: "✅",
    NOT_FOUND: "❌",
    UNCERTAIN: "⚠️",
    REQUIRES_REVIEW: "🔎",
}


@dataclass
class Citation:
    """A legal authority extracted from the draft."""

    raw_text: str
    type: str = UNKNOWN
    case_name: Optional[str] = None
    citation: Optional[str] = None  # neutral citation, e.g. "[2007] SGCA 37"
    act: Optional[str] = None
    section: Optional[str] = None
    order: Optional[str] = None
    rule: Optional[str] = None

    def query_text(self) -> str:
        """Text used to query the vector store."""
        parts = [
            self.case_name,
            self.citation,
            self.act,
            f"section {self.section}" if self.section else None,
            f"Order {self.order} Rule {self.rule}" if self.order and self.rule else None,
        ]
        joined = " ".join(p for p in parts if p)
        return joined or self.raw_text

    def key(self) -> str:
        """De-duplication key."""
        basis = self.citation or self.raw_text
        return " ".join(basis.lower().split())


@dataclass
class VerificationResult:
    citation: str
    type: str
    status: str
    confidence: float
    explanation: str
    source_title: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_url: Optional[str] = None
    manual_review_required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Report:
    summary: dict = field(default_factory=dict)
    results: list = field(default_factory=list)
    risk_level: str = "Unknown"
    risk_detail: str = ""
    disclaimer: str = ""

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "risk_level": self.risk_level,
            "risk_detail": self.risk_detail,
            "disclaimer": self.disclaimer,
            "results": [r.to_dict() for r in self.results],
        }


DISCLAIMER = (
    "QueLaw is a legal verification support tool. It does not provide legal "
    "advice and does not replace professional legal judgment. All flagged items "
    "should be manually reviewed against official legal sources before use."
)

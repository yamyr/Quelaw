"""Shared data types and the controlled vocabulary for statuses.

The wording of statuses is a hard requirement from the spec: never assert that a
case is "fake" or "good law". We only ever say it is or isn't *in the dataset*,
or that it needs manual review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

from .evidence_types import QuoteEvidence
from .provenance import Provenance

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
    start_char: int = -1
    end_char: int = -1
    quote_text: Optional[str] = None
    context_sentence: Optional[str] = None
    quote_ambiguous: bool = False

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
        """Authority identity, shared by separate occurrences in a draft."""
        if self.type == CASE and self.citation:
            return " ".join(self.citation.lower().split())
        if self.type == STATUTE and self.act and self.section:
            clean_act = " ".join(self.act.lower().split())
            return f"statute_{clean_act}_s_{self.section.lower()}"
        if self.type == RULE and self.order and self.rule:
            return f"rule_o{self.order.lower()}_r{self.rule.lower()}"
        basis = self.citation or self.raw_text
        return " ".join(basis.lower().split())

    def occurrence_key(self) -> tuple[int, int]:
        """Occurrence identity within the draft used to validate these offsets."""
        return self.start_char, self.end_char


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    """A reviewed replacement bound to one exact span and draft fingerprint."""

    draft_sha256: str
    start_char: int
    end_char: int
    expected_text: str
    replacement: str


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
    suggested_fix: Optional[str] = None
    quote_text: Optional[str] = None
    quote_evidence: QuoteEvidence | None = None
    external_search_url: Optional[str] = None
    start_char: int = -1
    end_char: int = -1
    source_id: str | None = None
    source_provenance: Provenance | None = None
    verifier: Literal["heuristic", "claude"] = "heuristic"
    fallback_reason: str | None = None
    occurrence_id: str = ""
    authority_key: str = ""
    context_sentence: str | None = None
    review_reasons: tuple[str, ...] = ()
    correction: CorrectionProposal | None = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["source_provenance"] = (
            self.source_provenance.model_dump(mode="json") if self.source_provenance else None
        )
        result["review_reasons"] = list(self.review_reasons)
        return result


@dataclass
class Report:
    schema_version: int = 2
    draft_sha256: str = ""
    dataset_fingerprint: str = ""
    verifier: dict[str, str | None] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    results: list[VerificationResult] = field(default_factory=list)
    risk_level: str = "Unknown"
    risk_detail: str = ""
    disclaimer: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "draft_sha256": self.draft_sha256,
            "dataset_fingerprint": self.dataset_fingerprint,
            "verifier": self.verifier,
            "summary": self.summary,
            "risk_level": self.risk_level,
            "risk_detail": self.risk_detail,
            "disclaimer": self.disclaimer,
            "results": [r.to_dict() for r in self.results],
        }


DISCLAIMER = (
    "Quelaw is a legal verification support tool. It does not provide legal "
    "advice and does not replace professional legal judgment. All flagged items "
    "should be manually reviewed against official legal sources before use."
)

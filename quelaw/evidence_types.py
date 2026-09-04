"""Typed external verdicts and bounded quotation evidence."""
from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


type AuthorityStatus = Literal[
    "verified", "not_found_in_dataset", "uncertain_match", "requires_manual_review",
]
type QuoteStatus = Literal[
    "match_in_available_text", "not_found_in_available_text", "evidence_limited", "ambiguous_attribution",
]
type NonEmptyText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


@dataclass(frozen=True, slots=True)
class QuoteEvidence:
    """A statement about available text, never quotation authentication."""

    status: QuoteStatus
    source_id: str | None
    matched_text: str | None
    reason: str


class ClaudeVerdict(BaseModel):
    """Model-supplied decisions must be typed before candidate validation."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, frozen=True, extra="forbid")

    status: AuthorityStatus
    confidence: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    explanation: NonEmptyText
    source_id: NonEmptyText | None
    source_excerpt: NonEmptyText | None
    manual_review_required: bool
    suggested_fix: NonEmptyText | None


class EvidenceValidationError(ValueError):
    """An external verdict references evidence unavailable in its candidates."""

    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)

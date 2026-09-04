"""Apply reviewed replacements only to their original draft and exact spans."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from .schema import CorrectionProposal


class StaleCorrectionError(ValueError):
    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class OverlappingCorrectionsError(ValueError):
    first_span: tuple[int, int]
    second_span: tuple[int, int]

    def __init__(self, first_span: tuple[int, int], second_span: tuple[int, int]) -> None:
        self.first_span = first_span
        self.second_span = second_span
        super().__init__(f"Correction spans overlap: {first_span} and {second_span}")


def apply_correction(draft: str, proposal: CorrectionProposal) -> str:
    """Apply a proposal or raise StaleCorrectionError without changing the draft."""
    return apply_corrections(draft, (proposal,))


def apply_corrections(draft: str, proposals: Sequence[CorrectionProposal]) -> str:
    """Validate the entire batch against the original draft before replacing text."""
    fingerprint = hashlib.sha256(draft.encode("utf-8")).hexdigest()
    ordered = sorted(proposals, key=lambda proposal: proposal.start_char)
    for proposal in ordered:
        if proposal.draft_sha256 != fingerprint:
            raise StaleCorrectionError("The draft has changed since this correction was reviewed.")
        if not 0 <= proposal.start_char < proposal.end_char <= len(draft):
            raise StaleCorrectionError("The correction span is outside the reviewed draft.")
        if draft[proposal.start_char:proposal.end_char] != proposal.expected_text:
            raise StaleCorrectionError("The correction span no longer contains the reviewed text.")
        if not proposal.replacement.strip():
            raise StaleCorrectionError("A correction must contain a nonempty replacement.")

    for first, second in zip(ordered, ordered[1:]):
        if second.start_char < first.end_char:
            raise OverlappingCorrectionsError(
                (first.start_char, first.end_char), (second.start_char, second.end_char),
            )

    updated = draft
    for proposal in reversed(ordered):
        updated = updated[:proposal.start_char] + proposal.replacement + updated[proposal.end_char:]
    return updated

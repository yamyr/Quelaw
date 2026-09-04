from __future__ import annotations

import hashlib
from typing import assert_never

from pydantic import ValidationError

from .annotator import StaleCorrectionError, apply_correction
from .evaluation_types import ClaudeCase, CorrectionCase, ExpectedQuote, Mismatch, QuoteCase
from .evidence import ClaudeVerdict, EvidenceValidationError, adapt_verdict, assess_quote
from .schema import Citation, CorrectionProposal


def evaluate_quote(case: QuoteCase) -> tuple[tuple[Mismatch, ...], str]:
    evidence = assess_quote(case.quote, case.source)
    actual = ExpectedQuote(
        status=evidence.status, source_id=evidence.source_id, matched_text=evidence.matched_text,
    )
    if not evidence.reason.strip():
        return (Mismatch(case_id=case.id, field="quote_reason", expected="nonempty reason", actual=evidence.reason),), evidence.status
    if actual == case.expected:
        return (), evidence.status
    return (Mismatch(case_id=case.id, field="quote_evidence",
                     expected=case.expected.model_dump(mode="json"), actual=actual.model_dump(mode="json")),), evidence.status


def evaluate_correction(case: CorrectionCase) -> tuple[Mismatch, ...]:
    proposal = CorrectionProposal(
        draft_sha256=hashlib.sha256(case.draft.encode()).hexdigest(),
        start_char=case.start_char, end_char=case.end_char,
        expected_text=case.expected_text, replacement=case.replacement,
    )
    try:
        actual_draft = apply_correction(case.edited_draft, proposal)
    except StaleCorrectionError:
        actual_draft = None
    actual = "stale_rejected" if actual_draft is None else "applied"
    failures: list[Mismatch] = []
    if actual != case.expected:
        failures.append(Mismatch(case_id=case.id, field="correction_outcome", expected=case.expected, actual=actual))
    if actual_draft != case.expected_draft:
        failures.append(Mismatch(case_id=case.id, field="corrected_draft", expected=case.expected_draft, actual=actual_draft))
    return tuple(failures)


def evaluate_claude(case: ClaudeCase) -> tuple[Mismatch, ...]:
    try:
        verdict = ClaudeVerdict.model_validate_json(case.payload)
        result = adapt_verdict(
            Citation(raw_text=case.draft, type="case", citation=case.draft, start_char=0, end_char=len(case.draft)),
            verdict, case.candidates,
        )
    except (ValidationError, EvidenceValidationError):
        match case.expected:
            case "rejected":
                return ()
            case "accepted":
                return (Mismatch(case_id=case.id, field="claude_outcome", expected="accepted", actual="rejected"),)
            case unreachable:
                assert_never(unreachable)
    failures: list[Mismatch] = []
    if case.expected != "accepted":
        failures.append(Mismatch(case_id=case.id, field="claude_outcome", expected=case.expected, actual="accepted"))
    if result.source_id != case.expected_source_id:
        failures.append(Mismatch(case_id=case.id, field="source_id", expected=case.expected_source_id, actual=result.source_id))
    for field, expected, actual in (
        ("status", verdict.status, result.status),
        ("manual_review_required", verdict.manual_review_required, result.manual_review_required),
        ("confidence", verdict.confidence, result.confidence),
        ("suggested_fix", verdict.suggested_fix, result.suggested_fix),
    ):
        if actual != expected:
            failures.append(Mismatch(case_id=case.id, field=field, expected=expected, actual=actual))
    selected = next((source for source in case.candidates if source.document_id == case.expected_source_id), None)
    if selected is not None:
        if result.source_title != selected.title or result.source_provenance != selected.provenance:
            failures.append(Mismatch(case_id=case.id, field="source_identity", expected=selected.document_id, actual=result.source_id))
        if not result.source_excerpt or not result.source_excerpt.strip() or result.source_excerpt not in selected.text:
            failures.append(Mismatch(case_id=case.id, field="source_excerpt", expected=selected.text, actual=result.source_excerpt))
        expected_url = str(selected.provenance.official_url) if selected.provenance.official_url else None
        if result.source_url != expected_url:
            failures.append(Mismatch(case_id=case.id, field="source_url", expected=expected_url, actual=result.source_url))
        if result.verifier != "claude":
            failures.append(Mismatch(case_id=case.id, field="verifier", expected="claude", actual=result.verifier))
    return tuple(failures)

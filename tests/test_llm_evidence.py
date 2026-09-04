"""The Claude boundary may select evidence but may not invent its identity."""
import json
from collections.abc import Sequence

import pytest
from pydantic import HttpUrl, ValidationError

from quelaw import evidence, llm, vectorstore
from quelaw.evidence_types import ClaudeVerdict
from quelaw.provenance import Dataset, Provenance, SourceRecord
from quelaw.schema import Citation, VERIFIED
from quelaw.verification import verify


@pytest.fixture
def candidates() -> tuple[SourceRecord, SourceRecord]:
    def record(number: int) -> SourceRecord:
        return SourceRecord(
            document_id=f"source-{number}", title=f"Candidate {number}", source_type="case",
            citation=f"[2020] SGCA {number}", source_url="sandbox://not-official",
            status="test", text=f"Evidence from candidate {number}. A second source sentence.",
            provenance=Provenance(
                text_kind="original", coverage="complete",
                official_url=HttpUrl(f"https://www.elitigation.sg/test/{number}"),
                retrieved_on=None, version_label=None, reuse_status="unverified",
                reuse_basis=None, limitations=("Synthetic test fixture.",),
            ),
        )
    return record(1), record(2)


def verdict_json(**changes: str | float | bool | None) -> str:
    fields = {
        "status": "verified", "confidence": 0.92, "explanation": "Matched candidate two.",
        "source_id": "source-2", "source_excerpt": "Evidence from candidate 2.",
        "manual_review_required": False, "suggested_fix": None,
    }
    fields.update(changes)
    return json.dumps(fields)


def test_selected_second_source_supplies_every_evidence_field(candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given a typed model verdict selecting the second candidate.
    citation = Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2", start_char=4, end_char=17)
    verdict = ClaudeVerdict.model_validate_json(verdict_json())
    # When it is adapted into a user-facing finding.
    result = evidence.adapt_verdict(citation, verdict, candidates)
    # Then metadata and excerpt are all bound to that same record.
    assert result.source_id == candidates[1].document_id
    assert result.source_title == candidates[1].title
    assert result.source_url == str(candidates[1].provenance.official_url)
    assert result.source_excerpt in candidates[1].text
    assert result.source_provenance == candidates[1].provenance
    assert result.verifier == "claude"


@pytest.mark.parametrize(("field", "value"), [
    ("confidence", "0.92"), ("confidence", float("nan")), ("confidence", float("inf")),
    ("confidence", -0.1), ("confidence", True), ("manual_review_required", "false"),
    ("explanation", 3), ("source_id", 2), ("status", "authenticated"),
])
def test_wrong_field_types_are_rejected_at_boundary(field: str, value: str | float | bool) -> None:
    # Given a malformed JSON value for a required verdict field.
    payload = verdict_json(**{field: value})
    # When the model response crosses the typed boundary.
    with pytest.raises(ValidationError):
        ClaudeVerdict.model_validate_json(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("source_id", "unknown"), ("source_excerpt", "Invented evidence."),
    ("suggested_fix", "Invented v Authority [2099] SGCA 100"),
])
def test_unsupported_evidence_is_rejected(candidates: tuple[SourceRecord, SourceRecord], field: str, value: str) -> None:
    # Given a syntactically valid verdict with unsupported evidence.
    verdict = ClaudeVerdict.model_validate_json(verdict_json(**{field: value}))
    # When it is compared with the actual candidate records.
    with pytest.raises(evidence.EvidenceValidationError):
        evidence.adapt_verdict(
            Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2"),
            verdict, candidates,
        )


def test_invalid_model_output_falls_back_with_visible_reason(monkeypatch: pytest.MonkeyPatch, candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given an explicit dataset and malformed Claude output.
    dataset = Dataset(records=candidates, fingerprint="test-fingerprint")
    def query(text: str, n_results: int, *, dataset: Dataset | None = None) -> Sequence[SourceRecord]:
        return candidates
    def message(system: str, user: str, max_tokens: int = 800) -> str:
        return verdict_json(manual_review_required="false")
    monkeypatch.setattr(vectorstore, "query", query)
    monkeypatch.setattr(llm, "_message", message)
    citation = Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2")
    # When verification encounters the invalid external response.
    result = verify(citation, use_llm=True, dataset=dataset)
    # Then deterministic checking uses the explicit dataset and explains fallback.
    assert result.status == VERIFIED
    assert result.source_id == "source-2"
    assert result.verifier == "heuristic"
    assert result.fallback_reason


def test_verified_verdict_is_rejected_when_source_is_a_different_authority(candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given a model-selected candidate with a different neutral citation.
    citation = Citation(raw_text="[2020] SGCA 1", type="case", citation="[2020] SGCA 1")
    verdict = ClaudeVerdict.model_validate_json(verdict_json())
    # When the model claims that unrelated candidate verifies the requested authority.
    with pytest.raises(evidence.EvidenceValidationError):
        evidence.adapt_verdict(citation, verdict, candidates)


def test_missing_excerpt_is_derived_from_selected_source(candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given a valid selected source with no model-supplied excerpt.
    citation = Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2")
    verdict = ClaudeVerdict.model_validate_json(verdict_json(source_excerpt=None))
    # When it is adapted for display.
    result = evidence.adapt_verdict(citation, verdict, candidates)
    # Then the displayed excerpt is a literal substring of the selected record.
    assert result.source_excerpt == candidates[1].text


def test_canonical_suggestion_is_grounded_in_selected_source(candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given an uncertain citation and a canonical replacement from source metadata.
    citation = Citation(raw_text="[2019] SGCA 2", type="case", citation="[2019] SGCA 2")
    verdict = ClaudeVerdict.model_validate_json(verdict_json(
        status="uncertain_match", suggested_fix="[2020] SGCA 2", manual_review_required=True,
    ))
    # When the suggested replacement is adapted.
    result = evidence.adapt_verdict(citation, verdict, candidates)
    # Then the proposal contains only the actual selected authority's neutral citation.
    assert result.suggested_fix == candidates[1].citation


@pytest.mark.parametrize("payload", [
    "not json", verdict_json(source_id="unknown"),
    verdict_json(source_excerpt="Evidence from candidate 1."),
    verdict_json(confidence=float("nan")),
])
def test_unusable_response_is_observable_in_pipeline_fallback(monkeypatch: pytest.MonkeyPatch, candidates: tuple[SourceRecord, SourceRecord], payload: str) -> None:
    # Given invalid external responses across parsing, identity and excerpt boundaries.
    dataset = Dataset(records=candidates, fingerprint="test-fingerprint")
    def query(text: str, n_results: int, *, dataset: Dataset | None = None) -> Sequence[SourceRecord]:
        return candidates
    def message(system: str, user: str, max_tokens: int = 800) -> str:
        return payload
    monkeypatch.setattr(vectorstore, "query", query)
    monkeypatch.setattr(llm, "_message", message)
    citation = Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2")
    # When the full verifier selects deterministic fallback.
    result = verify(citation, use_llm=True, dataset=dataset)
    # Then the fallback is reviewable while its source still comes from that dataset.
    assert result.verifier == "heuristic"
    assert result.source_id == "source-2"
    assert result.fallback_reason in result.review_reasons
    assert result.manual_review_required is True


def test_not_found_verdict_cannot_attach_a_selected_authority(candidates: tuple[SourceRecord, SourceRecord]) -> None:
    # Given a model claims no authority was found while attaching one as its evidence.
    citation = Citation(raw_text="[2020] SGCA 2", type="case", citation="[2020] SGCA 2")
    verdict = ClaudeVerdict.model_validate_json(verdict_json(status="not_found_in_dataset"))
    # When the contradictory verdict is adapted.
    with pytest.raises(evidence.EvidenceValidationError):
        evidence.adapt_verdict(citation, verdict, candidates)

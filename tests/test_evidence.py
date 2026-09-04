"""Quotation evidence is bounded by the fidelity and coverage of a source."""
import pytest

from quelaw import evidence
from quelaw.provenance import Coverage, Provenance, SourceRecord, TextKind
from quelaw.schema import Citation


def source(text_kind: TextKind = "original", coverage: Coverage = "complete") -> SourceRecord:
    return SourceRecord(
        document_id="sample", title="Sample authority", source_type="case",
        source_url="sandbox://placeholder", status="sandbox", citation="[2020] SGCA 1",
        text="The team will inspect the truck before loading the crates.",
        provenance=Provenance(
            text_kind=text_kind, coverage=coverage, official_url=None, retrieved_on=None,
            version_label=None, reuse_status="unverified", reuse_basis=None,
            limitations=("Synthetic test fixture representing original-text provenance.",),
        ),
    )


@pytest.mark.parametrize("kind", ["paraphrase", "synthetic"])
def test_exact_phrase_is_limited_when_source_is_not_original(kind: TextKind) -> None:
    # Given source wording that is explicitly not original authority text.
    record = source(text_kind=kind)
    # When an identical quotation is assessed.
    result = evidence.assess_quote("inspect the truck", record)
    # Then word equality cannot authenticate the quotation.
    assert result.status == "evidence_limited"
    assert result.matched_text is None


@pytest.mark.parametrize("quote", [
    "The team will not inspect the truck before loading the crates.",
    "The team will inspect the crates before loading the truck.",
    "The team will inspect the truck truck before loading the crates.",
])
def test_changed_word_sequence_is_not_found_when_complete_original_is_available(quote: str) -> None:
    # Given complete original-text coverage.
    record = source()
    # When changed word order, negation, or duplication is checked.
    result = evidence.assess_quote(quote, record)
    # Then word overlap cannot become a quotation match.
    assert result.status == "not_found_in_available_text"


def test_absence_is_limited_when_source_is_an_excerpt() -> None:
    # Given only an excerpt of original text.
    record = source(coverage="excerpt")
    # When a quotation does not occur in that excerpt.
    result = evidence.assess_quote("A different sentence", record)
    # Then absence from the full document is not asserted.
    assert result.status == "evidence_limited"


def test_match_retains_exact_source_span_when_format_is_normalized() -> None:
    # Given original text and a format-only variation.
    record = source(coverage="excerpt")
    # When the full normalized token sequence is present.
    result = evidence.assess_quote("INSPECT\t the truck, before—loading", record)
    # Then the evidence retains the actual contiguous source wording.
    assert result.status == "match_in_available_text"
    assert result.matched_text == "inspect the truck before loading"
    assert result.source_id == record.document_id


def test_attribution_is_ambiguous_when_sentence_has_multiple_authorities() -> None:
    # Given extraction has marked shared quote attribution as ambiguous.
    citation = Citation(raw_text="[2020] SGCA 1", quote_text="inspect the truck", quote_ambiguous=True)
    # When evidence is attached to a matched authority.
    result = evidence.quote_for_citation(citation, source())
    # Then no authority is silently assigned that quotation.
    assert result is not None
    assert result.status == "ambiguous_attribution"
    assert result.source_id is None


def test_rule_number_is_not_confirmed_by_a_longer_rule_number() -> None:
    # Given a dataset containing Rule 60 and no separate Rule 6.
    from quelaw.provenance import Dataset
    from quelaw.verification import verify
    record = source().model_copy(update={
        "source_type": "rule", "citation": None, "order": "6", "rule": "60",
        "title": "Rules of Court", "provision": "Order 6 Rule 60",
    })
    dataset = Dataset(records=(record,), fingerprint="rule-boundary-fixture")
    citation = Citation(raw_text="Order 6 Rule 6", type="rule", order="6", rule="6")
    # When checking Rule 6 against the explicit dataset.
    result = verify(citation, use_llm=False, dataset=dataset)
    # Then a prefix of a different rule identifier is not verified.
    assert result.status == "requires_manual_review"


def test_explicit_dataset_does_not_fall_back_to_bundled_authorities() -> None:
    # Given an explicit empty dataset, despite a bundled matching citation.
    from quelaw.provenance import Dataset
    from quelaw.verification import verify
    dataset = Dataset(records=(), fingerprint="empty-fixture")
    citation = Citation(raw_text="[2007] SGCA 37", type="case", citation="[2007] SGCA 37")
    # When the caller intentionally chooses that dataset.
    result = verify(citation, use_llm=False, dataset=dataset)
    # Then the bundled sandbox cannot supply an unintended match.
    assert result.status == "not_found_in_dataset"
    assert result.source_id is None


@pytest.mark.parametrize(("requested", "available"), [("141", "14(1)"), ("14(12)", "14(1)(2)")])
def test_distinct_subsection_structure_is_not_flattened(requested: str, available: str) -> None:
    # Given a source whose parenthesized subsection structure differs from the request.
    from quelaw.provenance import Dataset
    from quelaw.verification import verify
    record = source().model_copy(update={
        "source_type": "statute", "citation": None,
        "title": "Example Act", "section": available,
    })
    citation = Citation(raw_text=f"section {requested} of the Example Act", type="statute", act="Example Act", section=requested)
    # When the verifier compares complete section identifiers.
    result = verify(citation, use_llm=False, dataset=Dataset(records=(record,), fingerprint="subsection-fixture"))
    # Then digit equality cannot erase nested provision boundaries.
    assert result.status == "requires_manual_review"

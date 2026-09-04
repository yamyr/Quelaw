"""Word matching is a text operation and never an authority-verification status."""
import pytest

from quelaw.evidence import matching_span


@pytest.mark.parametrize("quote", [
    "The team will inspect the crates before loading the truck.",
    "The team will not inspect the truck before loading the crates.",
    "The team will inspect the truck truck before loading the crates.",
])
def test_changed_sequence_has_no_matching_span(quote: str) -> None:
    # Given words similar to source text but with a different order or meaning.
    text = "The team will inspect the truck before loading the crates."
    # When matching complete contiguous tokens.
    result = matching_span(quote, text)
    # Then overlapping vocabulary does not yield a source span.
    assert result is None


def test_noncontiguous_tokens_have_no_matching_span() -> None:
    # Given an interrupted token sequence.
    text = "The team will inspect the truck. They will check the paperwork before loading the crates."
    # When the interruption is omitted from the quotation.
    result = matching_span("The team will inspect the truck before loading the crates.", text)
    # Then the omission is not treated as punctuation normalization.
    assert result is None


@pytest.mark.parametrize(("quote", "text"), [
    ("load", "unload"), ("load", "loading"), ("a crate", "a crateship"),
    ("", "words"), ("...", "words"), ("words", "..."), ("words", ""),
])
def test_partial_or_empty_tokens_have_no_matching_span(quote: str, text: str) -> None:
    # Given a partial token or wordless input.
    # When matching complete tokens.
    result = matching_span(quote, text)
    # Then no source span is returned.
    assert result is None


@pytest.mark.parametrize(("quote", "expected"), [
    ("The team will inspect the truck before loading the crates.", "The team will inspect the truck before loading the crates"),
    ("inspect the truck before loading", "inspect the truck before loading"),
    ("  INSPECT\t the\n truck, before—loading! ", "inspect the truck before loading"),
    ("crates", "crates"),
])
def test_matching_span_preserves_source_wording(quote: str, expected: str) -> None:
    # Given source text with a complete normalized quoted sequence.
    text = "The team will inspect the truck before loading the crates."
    # When punctuation, case and whitespace differ.
    result = matching_span(quote, text)
    # Then the return value is actual source wording, without any verification claim.
    assert result == expected

import pytest

from quelaw.verification import _check_quote_match


@pytest.mark.parametrize(
    "quote",
    [
        "The team will inspect the crates before loading the truck.",
        "The team will not inspect the truck before loading the crates.",
        "The team will inspect the truck truck before loading the crates.",
    ],
    ids=["reordered", "negated", "repeated-token"],
)
def test_quote_is_not_found_when_word_overlap_changes_the_sentence(quote: str) -> None:
    # Given a synthetic sentence with similar words but different meaning.
    text = "The team will inspect the truck before loading the crates."

    # When the quotation is checked against that sentence.
    result = _check_quote_match(quote, text)

    # Then word overlap alone does not produce a match.
    assert result == "not_found"


def test_quote_is_not_found_when_matching_words_are_not_contiguous() -> None:
    # Given all quoted words separated by additional source wording.
    quote = "The team will inspect the truck before loading the crates."
    text = (
        "The team will inspect the truck. They will then check the paperwork "
        "before loading the crates."
    )

    # When the quotation is checked against the longer source.
    result = _check_quote_match(quote, text)

    # Then an interrupted sequence does not produce a match.
    assert result == "not_found"


@pytest.mark.parametrize(
    ("quote", "text"),
    [("load", "unload"), ("load", "loading"), ("a crate", "a crateship")],
    ids=["word-suffix", "word-prefix", "last-token-prefix"],
)
def test_quote_is_not_found_when_it_only_matches_part_of_a_token(
    quote: str, text: str
) -> None:
    # Given a quoted word that occurs only inside a different source word.
    # When the quotation is checked against the source.
    result = _check_quote_match(quote, text)

    # Then matching requires complete tokens at both ends.
    assert result == "not_found"


@pytest.mark.parametrize(
    "quote",
    [
        "The team will inspect the truck before loading the crates.",
        "inspect the truck before loading",
        "  INSPECT\t the\n truck, before—loading! ",
        "crates",
    ],
    ids=["complete-sentence", "contiguous-excerpt", "normalized-format", "last-token"],
)
def test_quote_matches_when_complete_tokens_are_contiguous(quote: str) -> None:
    # Given a synthetic source with an exact normalized sequence of quoted words.
    text = "The team will inspect the truck before loading the crates."

    # When the quotation is checked against the source.
    result = _check_quote_match(quote, text)

    # Then case, whitespace, and punctuation do not prevent a match.
    assert result == "verified"


@pytest.mark.parametrize(
    ("quote", "text"),
    [
        (None, "The team will inspect the truck."),
        ("", "The team will inspect the truck."),
        (" \n ", "The team will inspect the truck."),
        ("...", "The team will inspect the truck."),
        ("inspect the truck", None),
        ("inspect the truck", ""),
        ("inspect the truck", " \n "),
        ("inspect the truck", "..."),
    ],
)
def test_quote_has_no_status_when_either_input_has_no_words(
    quote: str | None, text: str | None
) -> None:
    # Given a missing or wordless quote or source.
    # When the quotation is checked against the source.
    result = _check_quote_match(quote, text)

    # Then there is no match assessment.
    assert result is None

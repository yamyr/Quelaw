"""Extraction unit tests (no vector DB or API key needed).

    py -3.14 -m pytest        # if pytest is installed
    py -3.14 tests/test_extraction.py   # targeted pytest runner
"""
import pathlib
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw.extraction import extract_citations, extract_with_regex  # noqa: E402
from quelaw.schema import CASE, RULE, STATUTE, Citation  # noqa: E402


def _by_type(citations, t):
    return [c for c in citations if c.type == t]


def test_full_case_citation():
    cites = extract_with_regex(
        "See Spandeck Engineering (S) Pte Ltd v Defence Science & Technology "
        "Agency [2007] SGCA 37 on the point."
    )
    cases = _by_type(cites, CASE)
    assert any(c.citation == "[2007] SGCA 37" for c in cases)
    assert any("Spandeck" in (c.case_name or "") for c in cases)


def test_bare_neutral_citation():
    cites = extract_with_regex("The decision in [2022] SGCA 15 is relevant.")
    assert any(c.citation == "[2022] SGCA 15" for c in _by_type(cites, CASE))


def test_statute_variants():
    a = extract_with_regex("under section 14 of the Civil Law Act")
    b = extract_with_regex("see s 300 Penal Code")
    assert any(c.section == "14" and "Civil Law Act" in (c.act or "") for c in _by_type(a, STATUTE))
    assert any(c.section == "300" and "Penal Code" in (c.act or "") for c in _by_type(b, STATUTE))


def test_rule_of_court():
    cites = extract_with_regex("pursuant to Order 9 Rule 6 of the Rules of Court")
    rules = _by_type(cites, RULE)
    assert any(c.order == "9" and c.rule == "6" for c in rules)


def test_preserves_three_occurrences_of_one_authority():
    # Given three separately reviewable occurrences.
    text = "[2007] SGCA 37; [2007] SGCA 37; [2007] SGCA 37"
    # When extraction runs.
    citations = extract_with_regex(text)
    # Then their occurrence spans differ while their authority identity agrees.
    assert [(c.start_char, c.end_char) for c in citations] == [(0, 14), (16, 30), (32, 46)]
    assert len({c.key() for c in citations}) == 1
    assert [c.occurrence_key() for c in citations] == [(0, 14), (16, 30), (32, 46)]


def test_case_citation_with_comma():
    cites = extract_with_regex(
        "In Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency, [2007] SGCA 37, the court held..."
    )
    cases = _by_type(cites, CASE)
    assert len(cases) == 1
    assert cases[0].citation == "[2007] SGCA 37"
    assert "Spandeck" in (cases[0].case_name or "")


def test_statute_with_subsection():
    cites = extract_with_regex("Pursuant to section 14(1) of the Civil Law Act and s 300(a) of the Penal Code.")
    statutes = _by_type(cites, STATUTE)
    assert any(c.section == "14(1)" and "Civil Law Act" in (c.act or "") for c in statutes)
    assert any(c.section == "300(a)" and "Penal Code" in (c.act or "") for c in statutes)


def test_rule_of_court_comma_and_abbreviation():
    c1 = extract_with_regex("under Order 9, Rule 6 of the Rules of Court")
    assert any(c.order == "9" and c.rule == "6" for c in _by_type(c1, RULE))

    c2 = extract_with_regex("pursuant to O. 9, r. 6 of the Rules of Court")
    assert any(c.order == "9" and c.rule == "6" for c in _by_type(c2, RULE))

    c3 = extract_with_regex("see O 9 r 6 of the ROC")
    assert any(c.order == "9" and c.rule == "6" for c in _by_type(c3, RULE))


def test_statute_occurrences_preserve_different_phrasing():
    text = "section 14 of the Civil Law Act ... later s 14 of the Civil Law Act"
    statutes = _by_type(extract_with_regex(text), STATUTE)
    assert len(statutes) == 2
    assert statutes[0].key() == statutes[1].key()


def test_quote_extraction_near_citation():
    text = (
        'In Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37, '
        'the Court of Appeal held that "factual foreseeability is a threshold requirement" for negligence.'
    )
    cites = extract_with_regex(text)
    assert len(cites) == 1
    assert cites[0].quote_text == "factual foreseeability is a threshold requirement"


def test_character_spans_recorded():
    text = "See [2022] SGCA 15 for guidance."
    cites = extract_with_regex(text)
    assert len(cites) == 1
    start, end = cites[0].start_char, cites[0].end_char
    assert start >= 0 and end > start
    assert text[start:end] == "[2022] SGCA 15"


def test_same_neutral_citation_retains_different_case_names_in_order():
    # Given a repeated neutral citation with a later name mismatch.
    text = "see Alpha v Beta [2016] SGCA 20; see Gamma v Delta [2016] SGCA 20"
    # When extraction runs.
    citations = extract_with_regex(text)
    # Then both names survive for separate verification.
    assert [c.case_name for c in citations] == ["Alpha v Beta", "Gamma v Delta"]
    assert citations[0].key() == citations[1].key()


def test_mixed_authorities_follow_draft_order():
    # Given the reverse of the extractor's historical pattern order.
    text = "Order 9 Rule 6; section 14 of the Civil Law Act; [2016] SGCA 20"
    # When extraction runs.
    citations = extract_with_regex(text)
    # Then review order follows the draft.
    assert [c.type for c in citations] == [RULE, STATUTE, CASE]


def test_multiline_reference_preserves_exact_raw_span():
    # Given a wrapped citation with irregular whitespace.
    text = "see Alpha v Beta [2016]\n  SGCA 20"
    # When extraction runs.
    citation = extract_with_regex(text)[0]
    # Then replacement has exact old text while authority fields are normalized.
    assert citation.raw_text == "Alpha v Beta [2016]\n  SGCA 20"
    assert text[citation.start_char:citation.end_char] == citation.raw_text
    assert citation.citation == "[2016] SGCA 20"


def test_claude_identical_excerpts_reanchor_to_distinct_actual_positions():
    # Given repeated references missed by regex and untrusted model offsets.
    text = "the Alpha decision; the Alpha\n decision; the Alpha decision"
    extra = [Citation(raw_text="Alpha decision", start_char=999, end_char=1013) for _ in range(3)]
    # When the real extraction merge consumes the model result.
    with patch("quelaw.llm.extract_citations", return_value=extra):
        citations = extract_citations(text, use_llm=True)
    # Then each excerpt is anchored once with its original whitespace.
    assert [(c.start_char, c.end_char) for c in citations] == [(4, 18), (24, 39), (45, 59)]
    assert [c.raw_text for c in citations] == ["Alpha decision", "Alpha\n decision", "Alpha decision"]


def test_claude_fabricated_text_is_discarded_even_with_plausible_offsets():
    # Given a fabricated model excerpt pointing to a real draft range.
    text = "Alpha decision"
    extra = [Citation(raw_text="Invented judgment", start_char=0, end_char=14)]
    # When the real merge validates the excerpt.
    with patch("quelaw.llm.extract_citations", return_value=extra):
        citations = extract_citations(text, use_llm=True)
    # Then fabricated raw text cannot become a finding.
    assert citations == []


def test_claude_overlapping_capture_does_not_duplicate_regex_occurrence():
    # Given model captures of one regex occurrence and one later novel reference.
    text = "see Alpha v Beta [2016] SGCA 20; Gamma decision"
    extra = [Citation(raw_text="[2016] SGCA 20"), Citation(raw_text="Gamma decision")]
    # When extraction combines the two routes.
    with patch("quelaw.llm.extract_citations", return_value=extra):
        citations = extract_citations(text, use_llm=True)
    # Then the complete regex capture wins the overlap.
    assert [c.raw_text for c in citations] == ["Alpha v Beta [2016] SGCA 20", "Gamma decision"]


@pytest.mark.parametrize("separator", [" and ", ",\nwith "])
def test_quote_attribution_is_ambiguous_with_two_authorities(separator: str):
    # Given one sentence, including a wrapped variant, attributing one quote twice.
    text = '[2016] SGCA 20' + separator + '[2007] SGCA 37 establish "a shared principle".'
    # When extraction determines quotation context.
    citations = extract_with_regex(text)
    # Then both findings retain the quote only as ambiguously attributed evidence.
    assert [c.quote_ambiguous for c in citations] == [True, True]
    assert [c.quote_text for c in citations] == ["a shared principle", "a shared principle"]


def test_quote_attribution_is_ambiguous_with_multiple_quotes():
    # Given competing quotations next to one authority.
    text = '[2016] SGCA 20 says "one principle" and "another principle".'
    # When extraction determines quotation context.
    citation = extract_with_regex(text)[0]
    # Then it cannot silently authenticate just the first quotation.
    assert citation.quote_ambiguous is True


def test_quote_context_survives_abbreviations_and_internal_punctuation():
    # Given punctuation that does not end the containing sentence.
    text = 'Prior sentence. Under O. 9, r. 6, the phrase "Stop. Then continue!"\nrequires care. Next sentence.'
    # When extraction determines quotation context.
    citation = extract_with_regex(text)[0]
    # Then a complete quote is associated with the correct containing sentence.
    assert citation.quote_text == "Stop. Then continue!"
    assert citation.context_sentence == 'Under O. 9, r. 6, the phrase "Stop. Then continue!"\nrequires care.'
    assert citation.quote_ambiguous is False


def test_quote_context_does_not_cross_paragraph_breaks():
    # Given an unquoted authority in another paragraph.
    text = '"a separate quotation"\n\n[2016] SGCA 20'
    # When extraction determines quotation context.
    citation = extract_with_regex(text)[0]
    # Then unrelated paragraph text is not attributed to the authority.
    assert citation.quote_text is None


@pytest.mark.parametrize(("opening", "closing"), [('"', '"'), ("“", "”")])
@pytest.mark.parametrize("terminal", [".", "!", "?"])
def test_citation_does_not_inherit_quote_from_preceding_sentence(
    opening: str, closing: str, terminal: str,
):
    # Given a complete quoted sentence followed by a citation in a new sentence.
    text = f"The court stated {opening}a prior sentence{terminal}{closing} [2016] SGCA 20 is later cited."
    # When the public extractor determines the later citation's context.
    citation = extract_citations(text, use_llm=False)[0]
    # Then the previous sentence supplies no quotation to that finding.
    assert citation.quote_text is None
    assert citation.quote_ambiguous is False
    assert citation.context_sentence == "[2016] SGCA 20 is later cited."


@pytest.mark.parametrize(("opening", "closing"), [('"', '"'), ("“", "”")])
def test_sentence_ending_quote_remains_with_its_preceding_authority(
    opening: str, closing: str,
):
    # Given two authorities in separate sentences, only the first supplying a quote.
    text = f"[2007] SGCA 37 states {opening}a prior sentence.{closing} [2016] SGCA 20 is later cited."
    # When context is attached to both citation occurrences.
    citations = extract_citations(text, use_llm=False)
    # Then the quote is retained with the first occurrence alone.
    assert [citation.quote_text for citation in citations] == ["a prior sentence.", None]
    assert [citation.quote_ambiguous for citation in citations] == [False, False]


def test_empty_quotation_marks_do_not_hide_a_real_quote():
    # Given empty quotation marks before a meaningful quotation.
    text = '[2016] SGCA 20 says "" then "a real quotation".'
    # When quotation context is extracted.
    citation = extract_with_regex(text)[0]
    # Then the sole actual quotation remains usable and unambiguous.
    assert citation.quote_text == "a real quotation"
    assert citation.quote_ambiguous is False


def test_wrapped_subsection_has_the_same_authority_key():
    # Given the same subsection with and without a wrapping space.
    text = "section 14\n (1) of the Civil Law Act; s 14(1) of the Civil Law Act"
    # When extraction separates occurrence text from parsed identity.
    citations = extract_with_regex(text)
    # Then the exact excerpt survives without changing the authority key.
    assert citations[0].raw_text == "section 14\n (1) of the Civil Law Act"
    assert [citation.section for citation in citations] == ["14(1)", "14(1)"]
    assert len({citation.key() for citation in citations}) == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

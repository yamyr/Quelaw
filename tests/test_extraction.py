"""Extraction unit tests (no vector DB or API key needed).

    py -3.14 -m pytest        # if pytest is installed
    py -3.14 tests/test_extraction.py   # plain-assert fallback runner
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw.extraction import extract_with_regex  # noqa: E402
from quelaw.schema import CASE, RULE, STATUTE  # noqa: E402


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


def test_dedupe():
    text = "[2007] SGCA 37 ... again [2007] SGCA 37"
    assert len(_by_type(extract_with_regex(text), CASE)) == 1


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


def test_statute_dedupe_different_phrasing():
    text = "section 14 of the Civil Law Act ... later s 14 of the Civil Law Act"
    statutes = _by_type(extract_with_regex(text), STATUTE)
    assert len(statutes) == 1


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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

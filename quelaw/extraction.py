"""Citation extraction.

Strategy from the spec: regex first for the obvious, well-formed Singapore
citations, then an optional LLM fallback to pick up less standard references.
The regex pass is deterministic and runs with zero dependencies, so the demo is
reproducible even fully offline.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import List

from .quote_context import attach_quote_context
from .schema import CASE, RULE, STATUTE, Citation

# A Singapore neutral citation: [YEAR] COURT NUMBER, e.g. [2007] SGCA 37,
# [2023] SGHC 100, [2020] SGHC(I) 5.
_COURT = r"SG[A-Z]{2,4}(?:\([A-Z]\))?"
_NEUTRAL = rf"\[(?P<year>\d{{4}})\]\s+(?P<court>{_COURT})\s+(?P<num>\d+)"

# Party names: a run of "name words" on each side of " v " / " v. ".
# A name word either contains an uppercase letter (so "Pte", "(S)", "ABC" match
# but lowercase sentence words like "in", "relies", "decision" do not), or is one
# of a few connectors that genuinely appear inside case names.
_NAME_WORD = r"(?:[A-Za-z0-9.'’/&()\-]*[A-Z][A-Za-z0-9.'’/&()\-]*|of|and|the|&)"
_PARTY = rf"{_NAME_WORD}(?:\s+{_NAME_WORD}){{0,14}}"
_CASE_FULL = re.compile(
    rf"(?P<name>{_PARTY}\sv\.?\s{_PARTY})(?:,\s*|\s+)(?P<cite>{_NEUTRAL})"
)
_NEUTRAL_RE = re.compile(_NEUTRAL)

# Statutory references. The "section" keyword is matched case-insensitively, but
# the Act name is matched case-sensitively so we only grab Title-cased names that
# end in Act / Code / Ordinance. Subsections (e.g. s 14(1), § 300(a)) are supported.
_SECTION = r"(?:[Ss]ections?|[Ss]ec\.?|[Ss]s?\.?|§)\s*(?P<section>\d+[A-Z]?(?:\s*\([0-9a-zA-Z]+\))*)"
_ACT = (
    r"(?P<act>(?:[A-Z][A-Za-z’'\-]+\s+){1,6}(?:Act|Code|Ordinance)"
    r"(?:\s+\d{4})?(?:\s+\(Cap\.?\s*\w+\))?)"
)
_STATUTE_RE = re.compile(
    rf"{_SECTION}\s*(?:of\s+the\s+|of\s+|under\s+the\s+|,?\s+){_ACT}"
)

# Rules of Court: Order N Rule M (of the Rules of Court), including commas and
# abbreviated forms (e.g. O. 9, r. 6 / O 9 r 6).
_RULE_RE = re.compile(
    r"(?:Order|O\.?)\s+(?P<order>\d+)[,\s]+\s*(?:Rule|r\.?)\s+(?P<rule>\d+)"
    r"(?:\s+of\s+the\s+Rules\s+of\s+Court(?:\s+\d{4})?|\s+of\s+the\s+ROC)?",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return " ".join(text.split()).strip(" ,.;")


def extract_with_regex(text: str) -> List[Citation]:
    citations: List[Citation] = []
    consumed_spans: list[tuple[int, int]] = []

    # 1. Full case references (name + neutral citation).
    for m in _CASE_FULL.finditer(text):
        start, end = m.span()
        citations.append(
            Citation(
                raw_text=m.group(0),
                type=CASE,
                case_name=_clean(m.group("name")),
                citation=_clean(m.group("cite")),
                start_char=start,
                end_char=end,
            )
        )
        consumed_spans.append(m.span("cite"))

    # 2. Bare neutral citations not already captured above.
    for m in _NEUTRAL_RE.finditer(text):
        if any(s <= m.start() and m.end() <= e for s, e in consumed_spans):
            continue
        start, end = m.span()
        citations.append(
            Citation(
                raw_text=m.group(0),
                type=CASE,
                citation=_clean(m.group(0)),
                start_char=start,
                end_char=end,
            )
        )

    # 3. Statutory references.
    for m in _STATUTE_RE.finditer(text):
        start, end = m.span()
        citations.append(
            Citation(
                raw_text=m.group(0),
                type=STATUTE,
                act=_clean(m.group("act")),
                section=re.sub(r"\s+", "", m.group("section")),
                start_char=start,
                end_char=end,
            )
        )

    # 4. Rules of Court.
    for m in _RULE_RE.finditer(text):
        start, end = m.span()
        citations.append(
            Citation(
                raw_text=m.group(0),
                type=RULE,
                order=m.group("order"),
                rule=m.group("rule"),
                start_char=start,
                end_char=end,
            )
        )

    return attach_quote_context(text, _dedupe(citations))


def _dedupe(citations: List[Citation]) -> List[Citation]:
    kept: list[Citation] = []
    for citation in sorted(citations, key=lambda c: (c.start_char, -c.end_char)):
        if not kept or citation.start_char >= kept[-1].end_char:
            kept.append(citation)
    return kept


def _anchor_extras(text: str, extras: list[Citation], existing: list[Citation]) -> list[Citation]:
    """Resolve model excerpts to unused draft spans; model offsets are only hints."""
    claimed = [citation.occurrence_key() for citation in existing]
    anchored: list[Citation] = []
    for citation in extras:
        if not citation.raw_text.strip():
            continue
        spans: list[tuple[int, int]] = []
        start, end = citation.occurrence_key()
        if 0 <= start < end <= len(text) and text[start:end] == citation.raw_text:
            spans.append((start, end))
        pattern = r"\s+".join(re.escape(part) for part in citation.raw_text.split())
        spans.extend(match.span() for match in re.finditer(pattern, text))
        for start, end in spans:
            if any(start < other_end and other_start < end for other_start, other_end in claimed):
                continue
            anchored.append(replace(citation, raw_text=text[start:end], start_char=start, end_char=end))
            claimed.append((start, end))
            break
    return anchored


def extract_citations(text: str, use_llm: bool | None = None) -> List[Citation]:
    """Extract legal authorities from ``text``.

    Always runs the regex pass. If ``use_llm`` is true (or None and a key is
    configured) the LLM pass augments the result with anything regex missed.
    """
    from . import config

    citations = extract_with_regex(text)

    want_llm = config.llm_enabled() if use_llm is None else use_llm
    if want_llm:
        try:
            from . import llm

            extra = llm.extract_citations(text)
            citations = _dedupe(citations + _anchor_extras(text, extra, citations))
        except Exception:
            # Never let an LLM/API hiccup break extraction — regex stands alone.
            pass

    return attach_quote_context(text, citations)

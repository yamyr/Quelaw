"""Citation extraction.

Strategy from the spec: regex first for the obvious, well-formed Singapore
citations, then an optional LLM fallback to pick up less standard references.
The regex pass is deterministic and runs with zero dependencies, so the demo is
reproducible even fully offline.
"""
from __future__ import annotations

import re
from typing import List

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
    rf"(?P<name>{_PARTY}\sv\.?\s{_PARTY})\s+(?P<cite>{_NEUTRAL})"
)
_NEUTRAL_RE = re.compile(_NEUTRAL)

# Statutory references. The "section" keyword is matched case-insensitively, but
# the Act name is matched case-sensitively so we only grab Title-cased names that
# end in Act / Code / Ordinance.
_SECTION = r"(?:[Ss]ections?|[Ss]ec\.?|[Ss]s?\.?|§)\s*(?P<section>\d+[A-Z]?)"
_ACT = (
    r"(?P<act>(?:[A-Z][A-Za-z’'\-]+\s+){1,6}(?:Act|Code|Ordinance)"
    r"(?:\s+\d{4})?(?:\s+\(Cap\.?\s*\w+\))?)"
)
_STATUTE_RE = re.compile(
    rf"{_SECTION}\s+(?:of\s+the\s+|of\s+|under\s+the\s+|,?\s+)?{_ACT}"
)

# Rules of Court: Order N Rule M (of the Rules of Court).
_RULE_RE = re.compile(
    r"Order\s+(?P<order>\d+)\s+Rule\s+(?P<rule>\d+)"
    r"(?:\s+of\s+the\s+Rules\s+of\s+Court)?",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    return " ".join(text.split()).strip(" ,.;")


def extract_with_regex(text: str) -> List[Citation]:
    citations: List[Citation] = []
    consumed_spans: list[tuple[int, int]] = []

    # 1. Full case references (name + neutral citation).
    for m in _CASE_FULL.finditer(text):
        citations.append(
            Citation(
                raw_text=_clean(m.group(0)),
                type=CASE,
                case_name=_clean(m.group("name")),
                citation=_clean(m.group("cite")),
            )
        )
        consumed_spans.append(m.span("cite"))

    # 2. Bare neutral citations not already captured above.
    for m in _NEUTRAL_RE.finditer(text):
        if any(s <= m.start() and m.end() <= e for s, e in consumed_spans):
            continue
        citations.append(
            Citation(raw_text=_clean(m.group(0)), type=CASE, citation=_clean(m.group(0)))
        )

    # 3. Statutory references.
    for m in _STATUTE_RE.finditer(text):
        citations.append(
            Citation(
                raw_text=_clean(m.group(0)),
                type=STATUTE,
                act=_clean(m.group("act")),
                section=m.group("section"),
            )
        )

    # 4. Rules of Court.
    for m in _RULE_RE.finditer(text):
        citations.append(
            Citation(
                raw_text=_clean(m.group(0)),
                type=RULE,
                order=m.group("order"),
                rule=m.group("rule"),
            )
        )

    return _dedupe(citations)


def _dedupe(citations: List[Citation]) -> List[Citation]:
    seen: dict[str, Citation] = {}
    for c in citations:
        seen.setdefault(c.key(), c)
    return list(seen.values())


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
            citations = _dedupe(citations + extra)
        except Exception:
            # Never let an LLM/API hiccup break extraction — regex stands alone.
            pass

    return citations

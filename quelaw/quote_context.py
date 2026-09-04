"""Conservative quotation attribution within the draft's sentence boundaries."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Final

from .schema import Citation

_QUOTES: Final = re.compile(r'"[^"]*"|“[^”]*”')
_ABBREVIATION: Final = re.compile(
    r"\b(?:v|o|r|s|ss|sec|secs|art|arts|no|nos|para|paras|cap|pte|ltd|mr|mrs|ms|dr|prof|e\.g|i\.e|cf|[A-Z])\.$",
    re.IGNORECASE,
)


def _sentence_spans(text: str, protected: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Single line breaks wrap; blank lines and unprotected terminal punctuation split."""
    boundaries = {0, len(text)}
    terminal = r'\n[ \t\r]*\n|[.!?]["”](?=\s+(?:[A-Z0-9]|\[)|$)|[.!?](?=\s|$)'
    for match in re.finditer(terminal, text):
        if any(start <= match.start() < end and match.end() < end for start, end in protected):
            continue
        if match.group() == "." and _ABBREVIATION.search(text[:match.end()]):
            continue
        boundaries.add(match.end())
    ordered = sorted(boundaries)
    return list(zip(ordered, ordered[1:]))


def attach_quote_context(text: str, citations: list[Citation]) -> list[Citation]:
    """Recompute context from validated occurrences, flagging competing attributions."""
    quotes = [quote for quote in _QUOTES.finditer(text) if quote.group()[1:-1].strip()]
    protected = [quote.span() for quote in quotes] + [c.occurrence_key() for c in citations]
    sentences = _sentence_spans(text, protected)
    contextual: list[Citation] = []
    for left, right in sentences:
        members = [c for c in citations if left <= c.start_char < right]
        nearby_quotes = [q for q in quotes if left <= q.start() and q.end() <= right]
        quote_text = None
        if nearby_quotes:
            quote = nearby_quotes[0]
            quote_text = quote.group()[1:-1].strip()
        ambiguous = bool(nearby_quotes) and (len(members) > 1 or len(nearby_quotes) > 1)
        contextual.extend(
            replace(c, context_sentence=text[left:right].strip(),
                    quote_text=quote_text, quote_ambiguous=ambiguous)
            for c in members
        )
    return contextual

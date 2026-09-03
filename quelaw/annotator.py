"""In-draft annotation and 1-click citation fix engine.

Renders an interactive, visually annotated version of the legal draft with
color-coded status badges and provides deterministic text-replacement utilities
for 1-click transcription fixes.
"""
from __future__ import annotations

import html
import re
from typing import List, Tuple

from .schema import (
    NOT_FOUND,
    REQUIRES_REVIEW,
    STATUS_ICON,
    STATUS_LABEL,
    UNCERTAIN,
    VERIFIED,
    VerificationResult,
)

_BADGE_STYLE = {
    VERIFIED: "background:#d4efdf;color:#145a32;border:1px solid #27ae60;",
    NOT_FOUND: "background:#fadbd8;color:#78281f;border:1px solid #e74c3c;",
    UNCERTAIN: "background:#fdebd0;color:#7e5109;border:1px solid #f39c12;",
    REQUIRES_REVIEW: "background:#d6eaf8;color:#1b4f72;border:1px solid #2980b9;",
}


def annotate_draft_html(draft: str, results: List[VerificationResult]) -> str:
    """Generate marked-up HTML of the draft with embedded citation badges and tooltips."""
    if not results or not draft.strip():
        escaped = html.escape(draft).replace("\n", "<br>")
        return f"<div style='font-family:serif;font-size:1.05rem;line-height:1.7;'>{escaped}</div>"

    # Find span positions for all results
    spans: List[Tuple[int, int, VerificationResult]] = []
    for r in results:
        if r.start_char >= 0 and r.end_char > r.start_char and r.start_char < len(draft):
            spans.append((r.start_char, r.end_char, r))
        else:
            # Fallback substring search
            idx = draft.find(r.citation)
            if idx != -1:
                spans.append((idx, idx + len(r.citation), r))

    # Sort spans by start offset (ascending)
    spans.sort(key=lambda x: x[0])

    # De-conflict any overlapping spans
    filtered_spans: List[Tuple[int, int, VerificationResult]] = []
    last_end = 0
    for s, e, r in spans:
        if s >= last_end:
            filtered_spans.append((s, e, r))
            last_end = e

    out_parts: List[str] = []
    curr = 0
    for s, e, r in filtered_spans:
        # Preceding text
        if s > curr:
            out_parts.append(html.escape(draft[curr:s]).replace("\n", "<br>"))

        style = _BADGE_STYLE.get(r.status, "background:#eaeded;color:#2c3e50;")
        icon = STATUS_ICON.get(r.status, "•")
        label = STATUS_LABEL.get(r.status, r.status)
        cite_text = html.escape(draft[s:e])
        expl = html.escape(r.explanation)

        badge_html = (
            f"<mark style='padding:2px 6px;border-radius:4px;{style}font-weight:600;' "
            f"title='{icon} {label}: {expl}'>"
            f"{cite_text} <span style='font-size:0.8em;'>[{icon} {label}]</span>"
            f"</mark>"
        )
        out_parts.append(badge_html)
        curr = e

    if curr < len(draft):
        out_parts.append(html.escape(draft[curr:]).replace("\n", "<br>"))

    rendered = "".join(out_parts)
    return (
        f"<div style='background-color:#ffffff;color:#1e293b;padding:1.25rem 1.5rem;"
        f"border-radius:8px;border:1px solid #e2e8f0;font-family:Georgia,serif;"
        f"font-size:1.02rem;line-height:1.75;box-shadow:0 1px 3px rgba(0,0,0,0.05);'>"
        f"{rendered}</div>"
    )


def apply_fix(draft: str, old_citation: str, new_citation: str) -> str:
    """Replace an occurrence of old_citation with new_citation in draft."""
    if not old_citation.strip() or not new_citation:
        return draft
    pattern = r"\s+".join(re.escape(part) for part in old_citation.split())
    return re.sub(pattern, lambda match: new_citation, draft, count=1)


def apply_all_fixes(draft: str, results: List[VerificationResult]) -> str:
    """Apply all suggested fixes from the verification results to the draft."""
    updated = draft
    for r in results:
        if r.suggested_fix and r.citation:
            updated = apply_fix(updated, r.citation, r.suggested_fix)
    return updated

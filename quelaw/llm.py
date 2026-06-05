"""Optional Claude layer.

Used for (a) an extraction fallback and (b) higher-quality verification grounded
in retrieved sources. Every entry point degrades gracefully: on any error it
returns None / [] so the caller falls back to the offline heuristic path.

The model is told to behave as a verification assistant, never a lawyer, and to
answer only from the retrieved sources (RAG) — not from memory.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional

from . import config
from .schema import CASE, RULE, STATUTE, UNKNOWN, Citation

SYSTEM_PROMPT = (
    "You are a legal citation verification assistant for Singapore legal "
    "materials. You do not provide legal advice. You only compare extracted "
    "legal references against the retrieved source materials you are given. "
    "If a citation is not found in the retrieved sources, say it is not found "
    "in the dataset. Do not invent cases, statutes, citations, or source "
    "references. If the retrieved source does not support a conclusion, mark it "
    "as requiring manual review. Never describe a case as 'fake'. Always return "
    "a single JSON object and nothing else."
)

_ALLOWED_STATUS = {
    "verified",
    "not_found_in_dataset",
    "uncertain_match",
    "requires_manual_review",
}


def _client():
    import anthropic

    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _message(system: str, user: str, max_tokens: int = 800) -> str:
    client = _client()
    resp = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system,
                # Cache the (static) system prompt across citations in a draft.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return None
    return None


# --- Extraction fallback --------------------------------------------------

_EXTRACT_SYSTEM = (
    "You extract Singapore legal authorities from text. Return a JSON array. "
    "Each item has: raw_text, type (one of case, statute, rule, unknown), and "
    "the relevant fields among case_name, citation, act, section, order, rule. "
    "Only include authorities actually present in the text. Do not invent any. "
    "Return only the JSON array."
)


def extract_citations(text: str) -> List[Citation]:
    try:
        raw = _message(_EXTRACT_SYSTEM, text, max_tokens=1000)
        data = _parse_json(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    valid_types = {CASE, STATUTE, RULE, UNKNOWN}
    out: List[Citation] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("raw_text"):
            continue
        ctype = item.get("type", UNKNOWN)
        out.append(
            Citation(
                raw_text=str(item["raw_text"]),
                type=ctype if ctype in valid_types else UNKNOWN,
                case_name=item.get("case_name"),
                citation=item.get("citation"),
                act=item.get("act"),
                section=str(item["section"]) if item.get("section") else None,
                order=str(item["order"]) if item.get("order") else None,
                rule=str(item["rule"]) if item.get("rule") else None,
            )
        )
    return out


# --- Verification ---------------------------------------------------------

def _format_sources(sources: List[dict]) -> str:
    if not sources:
        return "(No candidate sources were retrieved from the sandbox.)"
    lines = []
    for i, s in enumerate(sources, 1):
        m = s.get("metadata", {})
        lines.append(
            f"[{i}] title={m.get('title')!r} citation={m.get('citation')!r} "
            f"type={m.get('source_type')!r} section={m.get('section')!r} "
            f"provision={m.get('provision')!r}\n"
            f"    excerpt: {s.get('excerpt', '')[:500]}"
        )
    return "\n".join(lines)


def verify_citation(citation: Citation, sources: List[dict]) -> Optional[dict]:
    user = (
        f"Citation to verify: {citation.raw_text}\n"
        f"Parsed: type={citation.type}, case_name={citation.case_name}, "
        f"citation={citation.citation}, act={citation.act}, "
        f"section={citation.section}, order={citation.order}, rule={citation.rule}\n\n"
        f"Retrieved candidate sources from the trusted Singapore sandbox:\n"
        f"{_format_sources(sources)}\n\n"
        "Decide the verification status using ONLY the retrieved sources.\n"
        'Return JSON exactly: {"status": one of '
        '["verified","not_found_in_dataset","uncertain_match","requires_manual_review"], '
        '"confidence": number 0..1, "explanation": string (<=40 words, neutral, '
        'no overclaiming), "source_title": string or null, "source_excerpt": '
        'string or null, "manual_review_required": boolean}.\n'
        "Rules: use 'verified' only if a retrieved source clearly matches the SAME "
        "authority (same citation, or same Act and section). If a similar but not "
        "identical authority appears, use 'uncertain_match'. If nothing matches, "
        "use 'not_found_in_dataset' (never call it fake). If a source partly "
        "supports it, use 'requires_manual_review'."
    )
    try:
        raw = _message(SYSTEM_PROMPT, user)
        data = _parse_json(raw)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("status") not in _ALLOWED_STATUS:
        return None
    return data

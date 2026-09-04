"""Strict optional Claude boundaries for extraction and source-bound verdicts."""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import ClassVar, Literal

import anthropic
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from . import config
from .evidence_types import ClaudeVerdict, NonEmptyText
from .provenance import SourceRecord
from .schema import Citation

SYSTEM_PROMPT = (
    "You are a legal citation verification assistant for Singapore legal materials. "
    "Compare references only with the supplied candidate sources. Do not invent "
    "authorities, source text, metadata, or legal conclusions. Return one JSON object."
)


class ClaudeResponseError(ValueError):
    """The optional model boundary could not provide a usable typed response."""

    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _message(system: str, user: str, max_tokens: int = 800) -> str:
    """Own the SDK client and bound latency for this optional external call."""
    with anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=30.0, max_retries=0) as client:
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
    return "".join(block.text for block in response.content if block.type == "text")


def _json_body(text: str) -> str:
    """Permit only an enclosing Markdown code fence around an otherwise exact JSON body."""
    return re.sub(r"\A```(?:json)?\s*\n(.*?)\n```\Z", r"\1", text.strip(), flags=re.DOTALL)


class ExtractedCitation(BaseModel):
    """Typed metadata from extraction; raw spans are anchored by the extraction layer."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, frozen=True, extra="forbid")

    raw_text: NonEmptyText
    type: Literal["case", "statute", "rule", "unknown"] = "unknown"
    case_name: str | None = None
    citation: str | None = None
    act: str | None = None
    section: str | None = None
    order: str | None = None
    rule: str | None = None


_EXTRACT_SYSTEM = (
    "Extract Singapore legal authorities actually present in the text. Return a JSON array. "
    "Each item has raw_text, type (case, statute, rule, unknown), and relevant optional "
    "string fields case_name, citation, act, section, order, rule. Do not invent references."
)


def extract_citations(text: str) -> list[Citation]:
    """Reject malformed extraction metadata before any span can enter the draft model."""
    try:
        raw = _message(_EXTRACT_SYSTEM, text, max_tokens=1000)
        records = TypeAdapter(list[ExtractedCitation]).validate_json(_json_body(raw))
    except (anthropic.APIError, ConnectionError, TimeoutError, ValidationError):
        return []
    return [Citation(
        raw_text=record.raw_text, type=record.type, case_name=record.case_name,
        citation=record.citation, act=record.act, section=record.section,
        order=record.order, rule=record.rule,
    ) for record in records]


def _format_sources(sources: Sequence[SourceRecord]) -> str:
    return "\n".join(source.model_dump_json() for source in sources) or "No candidate sources available."


def verify_citation(citation: Citation, sources: Sequence[SourceRecord]) -> ClaudeVerdict:
    """Parse the model response once; adaptation validates it against actual candidates."""
    user = (
        f"Citation: {citation.raw_text}\nParsed: type={citation.type}, case_name={citation.case_name}, "
        f"citation={citation.citation}, act={citation.act}, section={citation.section}, "
        f"order={citation.order}, rule={citation.rule}\nNearby quote: {citation.quote_text!r}\n"
        f"Candidate sources (source_id must equal a document_id):\n{_format_sources(sources)}\n"
        "Return JSON with exactly these required fields: status (verified, not_found_in_dataset, "
        "uncertain_match, requires_manual_review), confidence (finite number from 0 through 1), "
        "explanation (nonempty string), source_id (candidate document_id or null when not found), "
        "source_excerpt (an exact contiguous source substring or null), manual_review_required "
        "(boolean), suggested_fix (null or exact canonical reference from source metadata). "
        "Use verified only for the same authority including the exact requested provision. "
        "Do not return source_title or source_url: these are derived from the selected record. "
        "Quotation evidence is checked independently and is not authenticated by your verdict."
    )
    try:
        raw = _message(SYSTEM_PROMPT, user)
        return ClaudeVerdict.model_validate_json(_json_body(raw))
    except ValidationError as error:
        fields = ", ".join(".".join(str(part) for part in detail["loc"]) or "response" for detail in error.errors())
        raise ClaudeResponseError(f"Claude response failed validation ({fields}); deterministic verification used.") from error
    except (anthropic.APIError, ConnectionError, TimeoutError) as error:
        raise ClaudeResponseError(f"Claude request unavailable ({type(error).__name__}); deterministic verification used.") from error

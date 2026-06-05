"""Verification logic.

For each extracted citation we always retrieve candidate sources from the vector
store (the RAG step). Then:

* If Claude is enabled, it decides the status grounded in those sources.
* Otherwise (or if the LLM call fails) a deterministic heuristic decides the
  status by matching the citation against the known sandbox authorities.

The heuristic is intentionally conservative and uses the controlled wording from
the spec — it never claims a case is fake, only that it is "not found in the
dataset".
"""
from __future__ import annotations

import re
from typing import List, Optional

from . import config, vectorstore
from .sandbox import documents_cached
from .schema import (
    CASE,
    NOT_FOUND,
    REQUIRES_REVIEW,
    RULE,
    STATUTE,
    UNCERTAIN,
    VERIFIED,
    Citation,
    VerificationResult,
)

_NOT_FOUND_EXPLANATION = (
    "This authority was not found in the trusted dataset. It may be "
    "hallucinated or outside the current sandbox. Manual review required."
)


# --- normalisation helpers ------------------------------------------------

def _norm_cite(s: Optional[str]) -> str:
    return " ".join((s or "").upper().split())


def _norm_section(s: Optional[str]) -> str:
    return re.sub(r"[^0-9a-z]", "", (s or "").lower())


def _name_tokens(s: Optional[str]) -> set:
    tokens = re.findall(r"[a-z0-9]+", (s or "").lower())
    stop = {"v", "vs", "pte", "ltd", "the", "of", "and", "co", "sdn", "bhd"}
    return {t for t in tokens if t not in stop and len(t) > 1}


def _name_overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _act_match(query_act: str, doc_title: str) -> bool:
    q = re.sub(r"\b(the|act|code|ordinance)\b", "", query_act.lower()).strip()
    t = re.sub(r"\b(the|act|code|ordinance)\b", "", doc_title.lower()).strip()
    if not q or not t:
        return False
    return q in t or t in q


def _excerpt(doc: dict, limit: int = 320) -> str:
    text = (doc.get("text") or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _retrieved_excerpt(sources: List[dict], limit: int = 320) -> Optional[str]:
    if not sources:
        return None
    text = (sources[0].get("excerpt") or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "") if text else None


# --- public entry point ---------------------------------------------------

def verify(citation: Citation, use_llm: bool | None = None) -> VerificationResult:
    sources = vectorstore.query(citation.query_text(), n_results=config.TOP_K)

    want_llm = config.llm_enabled() if use_llm is None else use_llm
    if want_llm:
        from . import llm

        verdict = llm.verify_citation(citation, sources)
        if verdict:
            return _result_from_llm(citation, verdict, sources)

    return _verify_heuristic(citation, sources)


def verify_all(citations: List[Citation], use_llm: bool | None = None) -> List[VerificationResult]:
    return [verify(c, use_llm=use_llm) for c in citations]


# --- LLM result adapter ---------------------------------------------------

def _result_from_llm(citation: Citation, verdict: dict, sources: List[dict]) -> VerificationResult:
    excerpt = verdict.get("source_excerpt") or _retrieved_excerpt(sources)
    source_url = None
    if sources:
        source_url = sources[0].get("metadata", {}).get("source_url") or None
    try:
        confidence = float(verdict.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    return VerificationResult(
        citation=citation.raw_text,
        type=citation.type,
        status=verdict["status"],
        confidence=max(0.0, min(1.0, confidence)),
        explanation=str(verdict.get("explanation", "")).strip() or _NOT_FOUND_EXPLANATION,
        source_title=verdict.get("source_title"),
        source_excerpt=excerpt,
        source_url=source_url,
        manual_review_required=bool(
            verdict.get("manual_review_required", verdict["status"] != VERIFIED)
        ),
    )


# --- heuristic (offline) verifier -----------------------------------------

def _verify_heuristic(citation: Citation, sources: List[dict]) -> VerificationResult:
    docs = documents_cached()
    if citation.type == CASE:
        return _verify_case(citation, docs, sources)
    if citation.type == STATUTE:
        return _verify_statute(citation, docs, sources)
    if citation.type == RULE:
        return _verify_rule(citation, docs, sources)
    return _not_found(citation)


def _verify_case(citation, docs, sources) -> VerificationResult:
    target = _norm_cite(citation.citation)

    # 1. Exact neutral-citation match.
    if target:
        for d in docs:
            if _norm_cite(d.get("citation")) == target:
                return VerificationResult(
                    citation=citation.raw_text,
                    type=CASE,
                    status=VERIFIED,
                    confidence=0.95,
                    explanation="Exact citation match found in the trusted sandbox dataset.",
                    source_title=d.get("title"),
                    source_excerpt=_excerpt(d),
                    source_url=d.get("source_url") or None,
                    manual_review_required=False,
                )

    # 2. Similar case name but a different citation -> uncertain.
    if citation.case_name:
        q_tokens = _name_tokens(citation.case_name)
        best, best_score = None, 0.0
        for d in docs:
            if d.get("source_type") != "case":
                continue
            score = _name_overlap(q_tokens, _name_tokens(d.get("title")))
            if score > best_score:
                best, best_score = d, score
        if best is not None and best_score >= 0.5:
            return VerificationResult(
                citation=citation.raw_text,
                type=CASE,
                status=UNCERTAIN,
                confidence=round(0.4 + 0.2 * best_score, 2),
                explanation=(
                    "A case with a similar name exists in the dataset but the "
                    "citation differs. Possible typo or mismatch — manual review required."
                ),
                source_title=best.get("title"),
                source_excerpt=_excerpt(best),
                source_url=best.get("source_url") or None,
                manual_review_required=True,
            )

    return _not_found(citation)


def _verify_statute(citation, docs, sources) -> VerificationResult:
    statutes = [d for d in docs if d.get("source_type") == "statute"]
    act_matches = [d for d in statutes if _act_match(citation.act or "", d.get("title", ""))]
    if act_matches:
        sec = _norm_section(citation.section)
        sec_matches = [d for d in act_matches if _norm_section(d.get("section")) == sec and sec]
        if sec_matches:
            d = sec_matches[0]
            return VerificationResult(
                citation=citation.raw_text,
                type=STATUTE,
                status=VERIFIED,
                confidence=0.9,
                explanation=f"Section {citation.section} of the {d.get('title')} was found in the trusted dataset.",
                source_title=f"{d.get('title')} — section {d.get('section')}",
                source_excerpt=_excerpt(d),
                source_url=d.get("source_url") or None,
                manual_review_required=False,
            )
        d = act_matches[0]
        return VerificationResult(
            citation=citation.raw_text,
            type=STATUTE,
            status=REQUIRES_REVIEW,
            confidence=0.5,
            explanation=(
                f"The {d.get('title')} exists in the dataset, but section "
                f"{citation.section} could not be confirmed. Manual review of the "
                "specific provision required."
            ),
            source_title=d.get("title"),
            source_excerpt=_excerpt(d),
            source_url=d.get("source_url") or None,
            manual_review_required=True,
        )
    return _not_found(citation, kind="statute")


def _verify_rule(citation, docs, sources) -> VerificationResult:
    rules = [d for d in docs if d.get("source_type") == "rule"]
    want = f"order {citation.order} rule {citation.rule}".lower()
    for d in rules:
        provision = (d.get("provision") or "").lower()
        if want and want in provision:
            return VerificationResult(
                citation=citation.raw_text,
                type=RULE,
                status=VERIFIED,
                confidence=0.9,
                explanation=f"{d.get('provision')} was found in the trusted dataset ({d.get('title')}).",
                source_title=f"{d.get('title')} — {d.get('provision')}",
                source_excerpt=_excerpt(d),
                source_url=d.get("source_url") or None,
                manual_review_required=False,
            )
    if rules:
        d = rules[0]
        return VerificationResult(
            citation=citation.raw_text,
            type=RULE,
            status=REQUIRES_REVIEW,
            confidence=0.4,
            explanation=(
                f"The {d.get('title')} is in the dataset, but Order {citation.order} "
                f"Rule {citation.rule} could not be confirmed. Manual review required."
            ),
            source_title=d.get("title"),
            source_excerpt=_excerpt(d),
            source_url=d.get("source_url") or None,
            manual_review_required=True,
        )
    return _not_found(citation, kind="rule")


def _not_found(citation, kind: str = "authority") -> VerificationResult:
    explanation = _NOT_FOUND_EXPLANATION
    if kind == "statute":
        explanation = "No matching statute was found in the trusted dataset. Manual review required."
    elif kind == "rule":
        explanation = "No matching rule was found in the trusted dataset. Manual review required."
    return VerificationResult(
        citation=citation.raw_text,
        type=citation.type,
        status=NOT_FOUND,
        confidence=0.2,
        explanation=explanation,
        source_title=None,
        source_excerpt=None,
        source_url=None,
        manual_review_required=True,
    )

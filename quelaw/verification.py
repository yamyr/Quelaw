"""Optional Claude checking with observable deterministic fallback."""
from __future__ import annotations

from collections.abc import Sequence

from . import config, vectorstore
from .evidence import adapt_verdict, attach_evidence
from .evidence_types import EvidenceValidationError
from .heuristic import verify_heuristic
from .provenance import Dataset
from .sandbox import load_current_dataset
from .schema import Citation, VerificationResult


def verify(citation: Citation, use_llm: bool | None = None, *, dataset: Dataset | None = None) -> VerificationResult:
    """Check one occurrence; explicit offline mode never touches retrieval or Claude."""
    available = dataset if dataset is not None else load_current_dataset()
    want_llm = config.llm_enabled() if use_llm is None else use_llm
    fallback_reason = None
    if want_llm:
        from . import llm
        try:
            sources = vectorstore.query(citation.query_text(), n_results=config.TOP_K, dataset=available)
            verdict = llm.verify_citation(citation, sources)
            return adapt_verdict(citation, verdict, sources)
        except (EvidenceValidationError, llm.ClaudeResponseError, vectorstore.IndexRebuildRequired) as error:
            fallback_reason = str(error)
    result = verify_heuristic(citation, available)
    result.fallback_reason = fallback_reason
    source = next((record for record in available.records if record.document_id == result.source_id), None)
    return attach_evidence(result, citation, source)


def verify_all(citations: Sequence[Citation], use_llm: bool | None = None, *, dataset: Dataset | None = None) -> list[VerificationResult]:
    """Check every occurrence against one immutable dataset snapshot."""
    available = dataset if dataset is not None else load_current_dataset()
    return [verify(citation, use_llm=use_llm, dataset=available) for citation in citations]

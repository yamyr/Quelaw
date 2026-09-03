from typing import Never

import pytest

from quelaw import config, llm, vectorstore
from quelaw.extraction import extract_citations
from quelaw.pipeline import check_draft
from quelaw.schema import VERIFIED
from quelaw.verification import verify


@pytest.mark.parametrize(
    ("use_llm", "api_key"),
    [(False, ""), (False, "configured-test-key"), (None, "")],
)
def test_memo_report_skips_retrieval_when_heuristic_mode_is_selected(
    monkeypatch: pytest.MonkeyPatch, use_llm: bool | None, api_key: str
) -> None:
    # Given an offline run and a retrieval service that must never be touched.
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", api_key)

    def unexpected_query(text: str, n_results: int) -> Never:
        pytest.fail(f"Heuristic mode queried the vector store: {text!r}")

    monkeypatch.setattr(vectorstore, "query", unexpected_query)
    draft = (config.DEMO_DIR / "test_memo.txt").read_text(encoding="utf-8")

    # When the bundled memo runs through the real pipeline.
    report, _ = check_draft(draft, use_llm=use_llm)

    # Then the complete report still matches the bundled answer key.
    assert report.summary == {
        "total": 10,
        "verified": 5,
        "not_found": 2,
        "uncertain": 1,
        "requires_review": 2,
    }
    assert report.risk_level == "High"


@pytest.mark.parametrize("use_llm", [True, None])
def test_verification_retrieves_and_falls_back_when_llm_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, use_llm: bool | None
) -> None:
    # Given enabled Claude verification with retrieval but an unavailable API.
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "configured-test-key")
    citation = extract_citations("See [2007] SGCA 37.", use_llm=False)[0]
    queries: list[tuple[str, int]] = []
    llm_attempts: list[int] = []

    def empty_query(text: str, n_results: int) -> list[Never]:
        queries.append((text, n_results))
        return []

    def unavailable_message(system: str, user: str, max_tokens: int = 800) -> Never:
        llm_attempts.append(max_tokens)
        raise ConnectionError

    monkeypatch.setattr(vectorstore, "query", empty_query)
    monkeypatch.setattr(llm, "_message", unavailable_message)

    # When verification falls back through the real heuristic verifier.
    result = verify(citation, use_llm=use_llm)

    # Then retrieval and Claude are attempted before the sandbox result returns.
    assert queries == [("[2007] SGCA 37", config.TOP_K)]
    assert len(llm_attempts) == 1
    assert result.status == VERIFIED

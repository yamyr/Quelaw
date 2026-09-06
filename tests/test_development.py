from __future__ import annotations

import runpy
from pathlib import Path
from typing import Never

import pytest

from quelaw import config, llm, sandbox
from quelaw.pipeline import check_draft
from quelaw.provenance import DatasetValidationError


def test_default_pipeline_sees_source_edits_between_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a default dataset that has already been checked in this process.
    original = (config.SANDBOX_DIR / "cases/case_spandeck.json").read_text()
    path = tmp_path / "source.json"
    path.write_text(original)
    monkeypatch.setattr(sandbox, "SANDBOX_DIR", tmp_path)
    before, _ = check_draft("[2007] SGCA 37", use_llm=False)

    # When source evidence changes before the next check.
    path.write_text(original.replace("Spandeck Engineering", "Updated Engineering"))
    after, _ = check_draft("[2007] SGCA 37", use_llm=False)

    # Then the report uses the new source identity and text without a restart.
    assert after.dataset_fingerprint != before.dataset_fingerprint
    assert after.results[0].source_title is not None
    assert after.results[0].source_title.startswith("Updated Engineering")
    assert before.results[0].source_title is not None
    assert before.results[0].source_title.startswith("Spandeck Engineering")


def test_default_pipeline_rejects_invalid_source_after_a_successful_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a source that was valid on the previous check.
    path = tmp_path / "source.json"
    path.write_bytes((config.SANDBOX_DIR / "cases/case_spandeck.json").read_bytes())
    monkeypatch.setattr(sandbox, "SANDBOX_DIR", tmp_path)
    check_draft("[2007] SGCA 37", use_llm=False)

    # When a developer leaves invalid JSON in that source.
    path.write_text("{")

    # Then the next check reports the source error instead of using old evidence.
    with pytest.raises(DatasetValidationError, match="source.json"):
        check_draft("[2007] SGCA 37", use_llm=False)


def test_smoke_script_stays_offline_with_a_configured_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    # Given a developer has Claude configured but is running a local smoke check.
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "configured-test-key")

    def unexpected_message(system: str, user: str, max_tokens: int = 800) -> Never:
        pytest.fail("The offline smoke script called Claude")

    monkeypatch.setattr(llm, "_message", unexpected_message)

    # When the actual script entry point executes.
    runpy.run_path(str(config.ROOT_DIR / "scripts/check_demo.py"), run_name="__main__")

    # Then it prints an offline report without touching Claude.
    output = capsys.readouterr().out
    assert "offline heuristic" in output
    assert "Overall risk:" in output

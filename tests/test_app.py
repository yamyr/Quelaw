from collections import Counter
from pathlib import Path
import socket
from typing import Never

import pytest
from streamlit.testing.v1 import AppTest

from quelaw import config, demo, vectorstore
from quelaw.schema import NOT_FOUND, REQUIRES_REVIEW, UNCERTAIN, VERIFIED


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AppTest:
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(vectorstore, "CHROMA_DIR", tmp_path / "chroma")

    def unexpected_connection(
        connection: socket.socket, address: str | tuple[str, int] | tuple[str, int, int, int]
    ) -> Never:
        pytest.fail(f"Offline app attempted a network connection: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", unexpected_connection)
    tested = AppTest.from_file(str(config.ROOT_DIR / "app.py"), default_timeout=15).run()
    assert not tested.exception
    return tested


def _check_draft(app: AppTest) -> AppTest:
    return next(
        button for button in app.button
        if button.label in ("▶️ Run scenario", "🔍 Check Draft")
    ).click().run()


def _load_scenario(app: AppTest, scenario: demo.Scenario) -> AppTest:
    app.toggle[0].set_value(True).run()
    return app.selectbox(key="demo_choice").select(scenario.title).run()


@pytest.mark.parametrize("scenario", demo.SCENARIOS, ids=lambda scenario: scenario.id)
def test_demo_report_when_scenario_is_run(app: AppTest, scenario: demo.Scenario) -> None:
    # Given a selected built-in scenario with a fresh, empty index.
    _load_scenario(app, scenario)

    # When the user runs the scenario.
    _check_draft(app)

    # Then its report, summary, risk, and both exports render successfully.
    assert not app.exception
    assert app.text_area[0].value == scenario.draft
    counts = Counter(expectation.status for expectation in scenario.expected)
    assert {metric.label: metric.value for metric in app.main.metric} == {
        "Total": str(len(scenario.expected)),
        "Verified": str(counts[VERIFIED]),
        "Not found": str(counts[NOT_FOUND]),
        "Uncertain": str(counts[UNCERTAIN]),
        "Needs review": str(counts[REQUIRES_REVIEW]),
    }
    assert any(
        f"Overall risk: {scenario.expected_risk}" in markdown.value
        for markdown in app.markdown
    )
    assert len(app.tabs) == 2
    assert len(app.download_button) == 2


def test_error_when_empty_draft_is_checked(app: AppTest) -> None:
    # Given a normal-mode editor containing only whitespace.
    app.text_area[0].set_value(" \n\t ").run()

    # When the user asks for verification.
    _check_draft(app)

    # Then validation prevents any report from appearing.
    assert not app.exception
    assert len(app.error) == 1
    assert not app.main.metric
    assert not app.download_button


def test_report_updates_when_user_edits_and_rechecks(app: AppTest) -> None:
    # Given a displayed report for the wrong-citation scenario.
    _load_scenario(app, demo.WRONG_CITATION)
    _check_draft(app)

    # When the user replaces the draft, the old report hides until another check.
    app.text_area[0].set_value(demo.CLEAN.draft).run()
    assert not app.main.metric
    assert not app.download_button
    _check_draft(app)

    # Then the report reflects the edited draft, not the scenario's original text.
    assert not app.exception
    assert app.text_area[0].value == demo.CLEAN.draft
    assert {metric.label: metric.value for metric in app.main.metric} == {
        "Total": "5", "Verified": "5", "Not found": "0", "Uncertain": "0",
        "Needs review": "0",
    }


@pytest.mark.parametrize("fix_button", ["fix_btn_0", "apply_all_fixes_btn"])
def test_report_verifies_when_suggested_fix_is_applied(app: AppTest, fix_button: str) -> None:
    # Given a report containing a wrong-year citation with a suggested fix.
    _load_scenario(app, demo.WRONG_CITATION)
    _check_draft(app)

    # When the user applies the correction and checks the edited draft.
    app.button(key=fix_button).click().run()
    assert "[2017] SGCA 20" in app.text_area[0].value
    assert "[2016] SGCA 20" not in app.text_area[0].value
    assert not app.main.metric
    _check_draft(app)

    # Then both authorities verify and the resolved correction is no longer offered.
    assert not app.exception
    assert {metric.label: metric.value for metric in app.main.metric} == {
        "Total": "2", "Verified": "2", "Not found": "0", "Uncertain": "0",
        "Needs review": "0",
    }
    assert all(button.key != fix_button for button in app.button)


@pytest.mark.parametrize("fix_button", ["fix_btn_0", "apply_all_fixes_btn"])
def test_fix_updates_editor_when_user_reintroduces_same_error(app: AppTest, fix_button: str) -> None:
    # Given a draft already corrected once, then manually edited back to the typo.
    _load_scenario(app, demo.WRONG_CITATION)
    _check_draft(app)
    app.button(key=fix_button).click().run()
    corrected_draft = app.text_area[0].value
    app.text_area[0].set_value(demo.WRONG_CITATION.draft).run()
    _check_draft(app)

    # When the user applies the same suggested correction again.
    app.button(key=fix_button).click().run()

    # Then the visible editor updates again and the previous report disappears.
    assert not app.exception
    assert app.text_area[0].value == corrected_draft
    assert not app.main.metric


@pytest.mark.parametrize("filename", ["test_memo.txt", "test_memo.docx"])
def test_uploaded_draft_preserves_manual_edits_when_rechecked(app: AppTest, filename: str) -> None:
    # Given a draft loaded through the real file uploader.
    content = (config.DEMO_DIR / filename).read_bytes()
    app.file_uploader[0].set_value((filename, content, "application/octet-stream")).run()
    assert "[2016] SGCA 20" in app.text_area[0].value

    # When the user replaces the uploaded text and asks for another report.
    app.text_area[0].set_value(demo.CLEAN.draft).run()
    assert app.text_area[0].value == demo.CLEAN.draft
    _check_draft(app)

    # Then the editor and report retain the user's changes.
    assert not app.exception
    assert app.text_area[0].value == demo.CLEAN.draft
    assert {metric.label: metric.value for metric in app.main.metric} == {
        "Total": "5", "Verified": "5", "Not found": "0", "Uncertain": "0",
        "Needs review": "0",
    }


@pytest.mark.parametrize("fix_label", ["💡 Quick Fix:", "✨ Apply All Fixes"])
def test_uploaded_draft_preserves_correction_when_rechecked(app: AppTest, fix_label: str) -> None:
    # Given a report for the bundled Word memo, with the upload still selected.
    content = (config.DEMO_DIR / "test_memo.docx").read_bytes()
    app.file_uploader[0].set_value(("test_memo.docx", content, "application/octet-stream")).run()
    _check_draft(app)

    # When the user applies a suggested correction and checks again.
    next(button for button in app.button if button.label.startswith(fix_label)).click().run()
    assert "[2017] SGCA 20" in app.text_area[0].value
    assert "[2016] SGCA 20" not in app.text_area[0].value
    assert not app.main.metric
    _check_draft(app)

    # Then the revised report verifies the corrected authority.
    assert not app.exception
    assert {metric.label: metric.value for metric in app.main.metric} == {
        "Total": "10", "Verified": "6", "Not found": "2", "Uncertain": "0",
        "Needs review": "2",
    }


@pytest.mark.parametrize("remove_first", [False, True])
def test_draft_reloads_when_same_file_is_selected_again(app: AppTest, remove_first: bool) -> None:
    # Given an uploaded draft that the user has edited.
    upload = ("draft.txt", demo.WRONG_CITATION.draft.encode(), "text/plain")
    app.file_uploader[0].set_value(upload).run()
    app.text_area[0].set_value(demo.CLEAN.draft).run()
    if remove_first:
        app.file_uploader[0].clear().run()
        assert app.text_area[0].value == demo.CLEAN.draft

    # When the user explicitly selects the same file again.
    app.file_uploader[0].set_value(upload).run()

    # Then a fresh upload intentionally replaces the edited draft.
    assert not app.exception
    assert app.text_area[0].value == demo.WRONG_CITATION.draft

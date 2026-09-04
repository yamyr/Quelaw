from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace

import pytest

from quelaw import annotator, schema


def _proposal(draft: str) -> schema.CorrectionProposal:
    return schema.CorrectionProposal(
        draft_sha256=hashlib.sha256(draft.encode()).hexdigest(),
        start_char=16, end_char=30, expected_text="[2016] SGCA 20",
        replacement="[2017] SGCA 20",
    )


def test_correction_changes_only_second_identical_occurrence():
    # Given three identical references and a proposal targeting the middle one.
    draft = "[2016] SGCA 20; [2016] SGCA 20; [2016] SGCA 20"
    proposal = _proposal(draft)
    # When the correction is applied.
    updated = annotator.apply_correction(draft, proposal)
    # Then first and third references are untouched.
    assert updated == "[2016] SGCA 20; [2017] SGCA 20; [2016] SGCA 20"


def test_correction_rejects_edited_draft():
    # Given a proposal from the previous draft version.
    draft = "[2016] SGCA 20; [2016] SGCA 20"
    proposal = _proposal(draft)
    # When applied to an edited version, then the original hash blocks it.
    with pytest.raises(annotator.StaleCorrectionError):
        annotator.apply_correction("Edited " + draft, proposal)


@pytest.mark.parametrize(
    "changes",
    [{"start_char": -1}, {"end_char": 90}, {"end_char": 16},
     {"expected_text": "[2015] SGCA 20"}, {"replacement": ""}, {"replacement": " \n "}],
    ids=["negative-start", "past-end", "empty-span", "wrong-text", "empty-fix", "blank-fix"],
)
def test_invalid_proposal_cannot_modify_draft(changes):
    # Given a proposal whose span, old text, or replacement is invalid.
    draft = "[2016] SGCA 20; [2016] SGCA 20"
    proposal = replace(_proposal(draft), **changes)
    # When applied, then typed validation prevents mutation.
    with pytest.raises(annotator.StaleCorrectionError):
        annotator.apply_correction(draft, proposal)


def test_batch_applies_different_length_replacements_at_original_spans():
    # Given adjacent proposals sharing the same original hash.
    draft = "Alpha Beta"
    fingerprint = hashlib.sha256(draft.encode()).hexdigest()
    proposals = [
        schema.CorrectionProposal(fingerprint, 0, 6, "Alpha ", "A "),
        schema.CorrectionProposal(fingerprint, 6, 10, "Beta", "Longer name"),
    ]
    # When the batch is applied.
    updated = annotator.apply_corrections(draft, proposals)
    # Then changing earlier lengths cannot shift later targets.
    assert updated == "A Longer name"


def test_batch_rejects_overlap_before_any_change():
    # Given valid proposals whose original spans overlap.
    draft = "Alpha Beta"
    fingerprint = hashlib.sha256(draft.encode()).hexdigest()
    proposals = [
        schema.CorrectionProposal(fingerprint, 0, 5, "Alpha", "A"),
        schema.CorrectionProposal(fingerprint, 0, 10, "Alpha Beta", "B"),
    ]
    # When the batch is applied, then the conflicting batch is rejected.
    with pytest.raises(annotator.OverlappingCorrectionsError):
        annotator.apply_corrections(draft, proposals)
    assert draft == "Alpha Beta"


def test_batch_rejects_stale_member_without_changing_valid_member():
    # Given one valid proposal and a later member from another draft.
    draft = "Alpha Beta"
    fingerprint = hashlib.sha256(draft.encode()).hexdigest()
    proposals = [
        schema.CorrectionProposal(fingerprint, 0, 5, "Alpha", "A"),
        schema.CorrectionProposal("stale", 6, 10, "Beta", "B"),
    ]
    # When the whole batch is validated, then no partial result is returned.
    with pytest.raises(annotator.StaleCorrectionError):
        annotator.apply_corrections(draft, proposals)
    assert draft == "Alpha Beta"
    assert proposals[0].expected_text == "Alpha"


def test_proposal_is_immutable():
    # Given the original proposal kept for review.
    proposal = _proposal("[2016] SGCA 20; [2016] SGCA 20")
    # When an action tries to alter it, then review identity is immutable.
    with pytest.raises(FrozenInstanceError):
        proposal.replacement = "Changed"


def test_correction_preserves_multiline_whitespace_outside_its_span():
    # Given an exact wrapped span; normalized text would not match it.
    draft = "before\n[2016]\n  SGCA 20\nafter"
    proposal = schema.CorrectionProposal(
        hashlib.sha256(draft.encode()).hexdigest(), 7, 23,
        "[2016]\n  SGCA 20", "[2017] SGCA 20",
    )
    # When applied by span.
    updated = annotator.apply_correction(draft, proposal)
    # Then only the selected text changes.
    assert updated == "before\n[2017] SGCA 20\nafter"

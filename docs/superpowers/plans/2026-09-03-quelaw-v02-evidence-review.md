# Quelaw 0.2 Evidence Review Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task by task. Implementation authorized by the user on 2026-09-04.

**Baseline:** Main after PRs [#11](https://github.com/yamyr/Quelaw/pull/11) and [#12](https://github.com/yamyr/Quelaw/pull/12), commit `5f14e0b8afb02d795607fe1d27cc1ac9d1ae4e76`.

**Goal:** Make each citation finding traceable to its occurrence, reviewed draft, and versioned source evidence across the app and exports.

**Architecture:** Keep the Streamlit application and deterministic offline pipeline. Validate source and Claude payloads with Pydantic v2 at their boundaries, retain typed internal results, and make every correction and report carry a draft/dataset identity.

**Tech Stack:** Python `>=3.14,<3.15`, Streamlit, ChromaDB, Anthropic SDK, Pydantic v2, uv, pytest, Streamlit AppTest, browser QA.

**Spec:** `../specs/2026-09-03-quelaw-v02-evidence-review-design.md`. Read the design alongside this plan.

## Global constraints

- Product spelling is **Quelaw**; Python identifiers use `quelaw`.
- Keep authority states `verified`, `not_found_in_dataset`, `uncertain_match`, and `requires_manual_review`.
- Offline mode must never call retrieval or Claude, even when credentials are configured.
- Initial installation may need a network; demo and evaluation execution after setup must not.
- Unknown provenance remains unknown. Existing placeholders and paraphrases must never be upgraded to authoritative text by relabelling.
- Draft contents stay in session memory by default. Only the user-triggered exports persist them.
- Keep Python `>=3.14,<3.15`, Pydantic `>=2.10,<3`, uv `>=0.12.7,<0.13`, and canonical CI/export uv `0.12.9` unless a separately verified dependency change requires adjustment.
- Keep Chroma embedded. Any Chroma HTTP server or multi-tenant deployment requires resolving the four documented advisories through a verified patched version or reviewed alternative first.
- Apply changes on a new `codex/` branch from the recorded merged baseline. Preserve unrelated work.

## Module ownership and sequence

| Task | Files | Independently observable result |
|---|---|---|
| 1 | new `quelaw/provenance.py`, existing `quelaw/sandbox.py`, sandbox JSON, new dataset tests | Validated, fingerprinted inventory with explicit source limits |
| 2 | `schema.py`, `extraction.py`, `annotator.py`, `app.py`, extraction/correction tests | Every occurrence retained; corrections address the reviewed span |
| 3 | new `quelaw/evidence.py`, `verification.py`, `llm.py`, `vectorstore.py`, evidence tests | Quotations and Claude findings reference actual available evidence |
| 4 | `schema.py`, `pipeline.py`, `report.py`, `app.py`, export/AppTest tests, design docs | One report contract rendered consistently in app and exports |
| 5 | new evaluation corpus/runner, CI, README, ROADMAP, changelog | Reproducible offline evaluation and a reviewable 0.2 release candidate |

Task 1 precedes Tasks 3 and 4. Task 2 can start after Task 1's interfaces are committed. Task 3 precedes Task 4; Task 5 accepts the finished report contract. Write focused regressions before implementation, retain existing tests, and commit each independently working task.

## Task 1: Validate source inventory and dataset identity

**Files:** Create `quelaw/provenance.py`, `scripts/check_dataset.py`, `tests/test_dataset.py`. Modify `quelaw/sandbox.py` and every record under `data/sandbox/`.

**Interfaces:** `load_dataset(root: Path) -> Dataset` returns validated records and a SHA-256 fingerprint. `Dataset` exposes `records: tuple[SourceRecord, ...]` and `fingerprint: str`. `SourceRecord` preserves existing document fields and adds required `provenance: Provenance`. `Provenance` exposes `text_kind: Literal["original", "paraphrase", "synthetic"]`, `coverage: Literal["complete", "excerpt", "summary"]`, `official_url: HttpUrl | None`, `retrieved_on: date | None`, `version_label: str | None`, `reuse_status: Literal["unverified", "permitted"]`, `reuse_basis: str | None`, and `limitations: tuple[str, ...]`.

- [ ] Add a fixture with a missing `provenance.text_kind`; assert the validation error names the input file and the missing field. Add duplicate `document_id` and contradictory `reuse_status="permitted"` without a basis cases.
- [ ] Add a canonical-fingerprint regression and run `uv run --locked pytest tests/test_dataset.py -q`; it must fail before the new loader exists.

```python
first = load_dataset(fixture_dir)
rewrite_json_keys_in_reverse_order(fixture_dir)
assert load_dataset(fixture_dir).fingerprint == first.fingerprint
change_source_text(fixture_dir, document_id="sample", text="Changed fixture text")
assert load_dataset(fixture_dir).fingerprint != first.fingerprint
```

The two fixture helpers live in `tests/test_dataset.py` and only rewrite temporary JSON fixtures. For canonicalization, serialize validated records with `record.model_dump(mode="json")` into the `records` list before hashing:

```python
payload = json.dumps(
    sorted(records, key=lambda record: record["document_id"]),
    sort_keys=True, separators=(",", ":"), ensure_ascii=False,
).encode("utf-8")
fingerprint = hashlib.sha256(payload).hexdigest()
```

- [ ] Implement strict Pydantic input models, validate unique IDs, and wrap boundary validation errors with the filename. Keep `load_documents()` as the existing internal adapter returning validated record dictionaries so callers remain functional during this task.
- [ ] Classify existing records from their actual text. Keep placeholder URLs out of `official_url`; retain their status in limitations. Use null dates and `reuse_status="unverified"` where evidence is unavailable. Do not fetch or rewrite source material merely to fill fields.
- [ ] Make `scripts/check_dataset.py` print the fingerprint and counts by fidelity/coverage; exit nonzero on invalid records. Run it plus dataset, pipeline, and demo tests. Commit `feat: validate sandbox provenance and dataset identity`.

## Task 2: Preserve citation occurrences and target corrections safely

**Files:** Modify `quelaw/schema.py`, `quelaw/extraction.py`, `quelaw/annotator.py`, `app.py`, `tests/test_extraction.py`, `tests/test_pipeline.py`, `tests/test_app.py`. Create `tests/test_corrections.py`.

**Interfaces:** Keep `Citation.key()` as authority identity, add occurrence identity from validated offsets. Add frozen `CorrectionProposal(draft_sha256: str, start_char: int, end_char: int, expected_text: str, replacement: str)`. Add `apply_correction(draft: str, proposal: CorrectionProposal) -> str` and `apply_corrections(draft: str, proposals: Sequence[CorrectionProposal]) -> str`, raising `StaleCorrectionError` or `OverlappingCorrectionsError` before any mutation.

- [ ] Replace the old authority-deduplication expectation with an occurrence contract: three copies of one citation produce three spans in document order. Retain a separate assertion that their `Citation.key()` values are equal. Add a same-neutral-citation/different-name case so later occurrences cannot disappear.
- [ ] Add the correction regression and run `uv run --locked pytest tests/test_extraction.py tests/test_corrections.py -q` to observe failure.

```python
text = "[2016] SGCA 20; [2016] SGCA 20; [2016] SGCA 20"
start = text.index("[2016]", text.index(";") + 1)
proposal = CorrectionProposal(
    draft_sha256=hashlib.sha256(text.encode()).hexdigest(),
    start_char=start, end_char=start + len("[2016] SGCA 20"),
    expected_text="[2016] SGCA 20", replacement="[2017] SGCA 20",
)
assert apply_correction(text, proposal) == "[2016] SGCA 20; [2017] SGCA 20; [2016] SGCA 20"
with pytest.raises(StaleCorrectionError):
    apply_correction("Edited " + text, proposal)
```

- [ ] Sort regex results by offset and deduplicate only matching/overlapping captures of the same occurrence. For Claude extraction, validate every returned raw span against the draft; do not use model-provided offsets without checking the exact text. Resolve multiple identical strings to their actual unclaimed positions.
- [ ] Validate all proposals against the original draft hash and exact span before applying any. Reject overlap, then apply in descending `start_char` order. The UI must show replacement previews and require a new check after application.
- [ ] Update summary labels to distinguish citation occurrences from distinct authorities. Preserve scenario expectations where drafts contain no repeated authorities. Run extraction/correction/pipeline/AppTest suites and a browser second-occurrence correction. Commit `feat: review and correct individual citation occurrences`.

## Task 3: Bind quotations and Claude results to source evidence

**Files:** Create `quelaw/evidence.py`, `tests/test_evidence.py`, `tests/test_llm_evidence.py`. Modify `quelaw/verification.py`, `quelaw/llm.py`, `quelaw/vectorstore.py`, `quelaw/schema.py`, and quote tests.

**Interfaces:** `QuoteEvidence` contains `status: Literal["match_in_available_text", "not_found_in_available_text", "evidence_limited", "ambiguous_attribution"]`, `source_id: str | None`, `matched_text: str | None`, and `reason: str`. `assess_quote(quote: str, source: SourceRecord) -> QuoteEvidence` consumes Task 1 records. A typed Claude verdict references `source_id` equal to a candidate `SourceRecord.document_id` from the supplied set and uses validated string/boolean/status fields. `VerificationResult` carries `source_id`, source provenance, `quote_evidence`, `verifier: Literal["heuristic", "claude"]`, and an optional fallback reason.

- [ ] Add tests that an exact phrase in a paraphrase is `evidence_limited`, a negated/reordered phrase never becomes a match, and an absent phrase in an excerpt does not claim absence from the full document. Add a sentence containing two authorities and one quote: attribution is ambiguous rather than assigned to both automatically.
- [ ] Add a mocked Claude verdict selecting candidate two. Assert source ID, title, URL, and excerpt all come from candidate two. Unknown IDs, wrong field types, non-finite confidence, and unsupported excerpts must fail validation or return a visible deterministic fallback.

```python
result = adapt_verdict(citation, verdict_for_source_2, candidates)
assert result.source_id == candidates[1].document_id
assert result.source_url == str(candidates[1].provenance.official_url)
assert result.source_excerpt in candidates[1].text
assert result.verifier == "claude"
```

`adapt_verdict` is implemented in `quelaw/evidence.py`; its signature accepts the existing `Citation`, the new typed `ClaudeVerdict`, and `Sequence[SourceRecord]`, returning `VerificationResult`. The fixtures are defined in `tests/test_llm_evidence.py` using two distinct source records.

- [ ] Run `uv run --locked pytest tests/test_evidence.py tests/test_llm_evidence.py -q` to establish red; implement conservative quote states and candidate-identity validation. Never display an LLM-invented excerpt as retrieved evidence.
- [ ] Persist dataset fingerprint and source ID in retrieval metadata. Refuse to use an index with another fingerprint; show a rebuild-required state for Claude mode while offline checks remain usable. Rebuild explicitly through the existing ingest action.
- [ ] Run quote/offline/pipeline tests and a temporary real Chroma ingest/query driver. Live Claude is optional and must be identified separately from mocked-boundary validation. Commit `feat: bind findings to available source evidence`.

## Task 4: Render a consistent review workspace and export contract

**Files:** Modify `quelaw/schema.py`, `quelaw/pipeline.py`, `quelaw/report.py`, `app.py`, `tests/test_app.py`, and `docs/DESIGN.md`. Create `tests/test_report_exports.py`.

**Interfaces:** Report schema version `2` includes `draft_sha256`, `dataset_fingerprint`, `verifier` metadata, occurrence and distinct-authority counts, findings, and review flags. `report_to_markdown(report: Report) -> str` renders the same material evidence as `Report.to_dict()`. The UI consumes this report directly and keeps the current session-only draft lifetime.

- [ ] Add a report fixture containing a repeated authority, uncertain citation, evidence-limited quotation, and correction proposal. Assert every finding's ID, status, source ID, review reason, quotation state, and proposed replacement appears in JSON and Markdown. Add dataset/draft fingerprint equality checks.
- [ ] Define risk consistently: preserve High for a not-found authority; at least Medium when any authority or quote needs review; Low only when all available findings meet the defined dataset checks. Keep the wording scoped to available evidence. Add tests for verified authority plus evidence-limited quote.
- [ ] Run `uv run --locked pytest tests/test_report_exports.py tests/test_app.py -q` to establish red, then implement the report fields and serializers. Bump the export schema version explicitly; do not silently reinterpret version 1 fields.
- [ ] Add a finding selector beside the annotated draft/evidence view. Show occurrence context, source fidelity/coverage, source links, quote limits, replacement preview, and review reason. Use native Streamlit controls and labels; update `docs/DESIGN.md` to match the resulting screen.
- [ ] Verify browser keyboard use, edit/report invalidation, second-occurrence correction, download parity, and the 390 px mobile layout. Commit `feat: add traceable evidence review and report exports`.

## Task 5: Establish offline evaluation and the 0.2 release gate

**Files:** Create `data/evaluation/v1/cases.jsonl`, `data/evaluation/v1/README.md`, `data/evaluation/v1/baseline.json`, `scripts/evaluate.py`, `tests/test_evaluation.py`, and `CHANGELOG.md`. Modify CI, README, CONTRIBUTING, and ROADMAP.

**Interfaces:** Each evaluation case stores `id`, `draft`, expected occurrences with offsets/type/parsed fields, expected authority/quote states, failure category, and reviewer status. `uv run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json` produces a JSON summary and exits nonzero on unapproved expectation differences. No network or API access is allowed in this command.

- [ ] Create at least 30 independently specified cases across exact matches, absent/out-of-scope authorities, citation/name mismatches, nested subsections, repeated references, stale corrections, quote transformations, ambiguous attribution, incomplete evidence, and malformed mocked Claude outputs. Keep fabricated fixtures identified as synthetic.
- [ ] Separate extraction precision/recall and span accuracy from verification confusion counts and quote outcomes. Compare all material expected fields; a small aggregate score increase must not hide a new false verification. Mark legal expectations awaiting domain review rather than claiming they are validated.
- [ ] Add a regression that changes one expected verified result to a mismatch and asserts nonzero evaluation exit status; add a no-network evaluation test. Run `uv run --locked pytest tests/test_evaluation.py -q` red, then implement the runner and commit the reviewed engineering baseline.
- [ ] Recheck the four documented Chroma advisories against the installed version. Keep unresolved findings visible and do not dismiss them solely because the current deployment is embedded.
- [ ] Add dataset validation, offline evaluation, full tests, undefined-name lint, and export drift checks to CI. Add Ruff as a locked development dependency before invoking its undefined-name check (`uv run --locked ruff check --select F821 app.py quelaw scripts tests`) Run a fresh locked install and all existing demo flows on the supported Python runtime. Record source fingerprint, report schema version, limitations, and evaluation reviewer status in the changelog.
- [ ] Require the release demonstration: upload a memo, select a repeated citation, inspect provenance, apply one correction, recheck, and download matching Markdown/JSON evidence. Independent review and green CI precede a `v0.2.0` tag. Tagging and deployment require the later implementation task's release instruction; this plan does not execute them.

## Completion checklist

- [ ] Every release acceptance case in the design has an automated regression or a recorded browser scenario.
- [ ] No source dates, permissions, legal holdings, or quotation authenticity were invented.
- [ ] Invalid/stale source and draft identities produce visible review states instead of confident findings.
- [ ] Current offline demo behavior remains reproducible without an index or API key.
- [ ] Domain-review gaps are recorded before any accuracy or coverage claim.
- [ ] All five changes are reviewed, CI passes, and the release notes state what was and was not tested.

## First implementation step

Start with Task 1, source validation and dataset identity. It makes the current nine-entry sandbox inspectable and provides the evidence contract required by every subsequent step.

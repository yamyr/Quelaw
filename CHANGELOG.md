# Changelog

## Unreleased — development workflow (2026-09-06)

- Add shared Make targets for setup, offline app development, focused tests, fast checks, the complete CI gate, dependency upgrades and export verification. Cancel obsolete CI runs on the same branch.
- Load fresh source evidence for every default pipeline/verification call, preserving explicit dataset snapshots for batches. Invalid source edits fail on the next check instead of reusing cached evidence.
- Force the golden-path smoke command offline even when Claude credentials are configured.
- Upgrade Anthropic 1.3.0 → 1.4.0, AnyIO 4.15.0 → 4.15.1, googleapis-common-protos 1.75.2 → 1.75.3, and NumPy 2.5.2 → 2.5.3; regenerate the runtime export. The [Anthropic release notes](https://github.com/anthropics/anthropic-sdk-python/releases/tag/v1.4.0) describe the SDK changes. Other packages remain within their parent constraints.
- Recheck the four ChromaDB advisory pages on 2026-09-06: all still list no patched version. ChromaDB remains 1.5.9 with the limitations documented below.

## 0.2.0 — untagged release candidate (2026-09-04)

This candidate adds occurrence-specific evidence review and a repeatable engineering evaluation. It is not a published release. Independent review, green CI, and the [release demonstration](CONTRIBUTING.md#release-demonstration) are required before a `v0.2.0` tag; tagging and deployment require an explicit release instruction.

### Evidence and review contract

- Validate every source record and its provenance, reject duplicate IDs and invalid metadata, and compute a canonical dataset SHA-256 fingerprint.
- Retain repeated citation occurrences in draft order and separate occurrence counts from distinct-authority counts.
- Bind correction proposals to the reviewed draft SHA-256, offsets, and expected text. Applying one proposal changes only that occurrence; stale and overlapping proposals fail before any change. Draft edits invalidate findings and require rechecking.
- Separate quotation evidence from authority matching. Exact text in a paraphrase is evidence-limited; incomplete sources cannot prove a quotation absent from the full document; ambiguous attribution requires review.
- Bind optional Claude verdicts to validated candidate source IDs, exposing deterministic fallback reasons for malformed or unsupported results. Index identity must match the dataset fingerprint before retrieval.
- Export report schema **`2`**, with the same material evidence in the app, Markdown, and JSON: draft/dataset identities, verifier metadata, occurrence/distinct-authority counts, finding and source IDs, review flags, quote evidence, and correction proposals. Schema `1` consumers must migrate explicitly.

### Dataset identity and limits

- Dataset: `data/sandbox/`, **9 records**, comprising **5 paraphrases and 4 synthetic entries**; every record has `coverage="summary"`.
- Dataset fingerprint checked on 2026-09-04 with `uv run --locked python scripts/check_dataset.py`: `36e49d62e83e21e23c4e9b0671c6af70831c4e4092b1aa70ba7efa0cd44a7638`.
- No complete official text is bundled. All records have null `official_url`, `retrieved_on`, `version_label`, and `reuse_basis`, with `reuse_status="unverified"`. Legacy dates and placeholder URLs are not verified provenance or reuse permission.
- The [inventory](README.md#dataset-and-provenance) identifies each entry. No legal holdings, source dates, permissions, current-law status, or quotation authenticity have been established by these engineering changes.

### Evaluation and release evidence

The versioned [evaluation corpus](data/evaluation/v1/README.md) contains 48 independently specified engineering fixtures: 33 pipeline cases with 37 expected citation occurrences, plus 15 controlled quote/correction/Claude-boundary cases. Legal expectations are marked **`reviewer_status="legal_domain_review_pending"`**. The committed engineering baseline supports regression review; it is not a legal accuracy benchmark.

```bash
uv run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json
```

This command permits no network or API access, and requires no embedding download or vector index after dependency setup. It reports extraction precision/recall and span accuracy separately from verification confusion counts and quotation outcomes, and returns a nonzero exit for material unapproved expectation differences. Fixtures cover exact/absent/out-of-scope authorities, mismatches, nested provisions, repeated references, stale corrections, transformed/ambiguous quotations, incomplete evidence, and malformed mocked Claude outputs.

CI uses locked dependencies and adds dataset validation, offline evaluation, full tests, demo checks, Ruff `F821` undefined-name lint from the locked development group, and runtime requirements export drift verification. Automated and mocked-boundary checks do not establish live Claude behavior or legal accuracy. Record fresh install, runtime/retrieval/API checks, browser demonstration, independent review, and CI results for the final candidate commit before release approval; this entry does not claim those gates have passed.

Local integration checks on 2026-09-04 used a fresh locked Python 3.14.4 environment with uv 0.12.9: 196 tests passed, all 48 evaluation cases matched, all four demo scenarios passed, and the golden-path smoke run remained offline. Dependency compatibility, compilation, Ruff `F821`, and requirements export drift checks passed. ChromaDB emitted one upstream `asyncio.iscoroutinefunction` deprecation warning. These local checks do not establish remote CI or release-demonstration approval; live Claude was not exercised by the offline evaluation.

Final review added seven rendering regressions, bringing the suite to 203 passing tests. Exported scalar values and review reasons now preserve untrusted Markdown and HTML as literal text; the actual browser download was checked with a CommonMark renderer. Package version metadata and the design guide now agree with the 0.2.0 candidate.

### Unresolved ChromaDB advisories

On **2026-09-04**, the installed `.venv` package and `uv.lock` both identify **`chromadb==1.5.9`**. The GitHub Global Advisory API was rechecked for all four advisories below. Each includes version 1.5.9 in its affected range, is not withdrawn, and lists `first_patched_version: null`.

| Advisory | Severity | Affected versions | Upstream last updated | Patched version |
|---|---|---|---|---|
| [GHSA-f4j7-r4q5-qw2c — pre-authentication code injection](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | Critical | `>=1.0.0, <=1.5.9` | 2026-05-29 | None listed |
| [GHSA-36p7-vc44-83pf — code injection](https://github.com/advisories/GHSA-36p7-vc44-83pf) | Critical | `>=0.4.17, <=1.5.9` | 2026-08-24 | None listed |
| [GHSA-2wm9-hf6c-p5cr — cross-tenant collection access](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | High | `>=0.4.17, <=1.5.9` | 2026-08-24 | None listed |
| [GHSA-xph7-9rjv-w5fr — SimpleRBAC authorization scoping](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | High | `>=0.5.0, <=1.5.9` | 2026-08-24 | None listed |

Quelaw constructs an embedded local `PersistentClient`; it does not launch the Chroma HTTP endpoints or server authorization paths described by these advisories. That deployment shape limits those described attack paths but does **not** resolve or dismiss any package advisory. Keep all four findings visible. A Chroma HTTP server or multi-tenant deployment requires a verified patched version or a reviewed alternative, followed by lock/export updates and relevant runtime/security checks. The current candidate is not security-certified.

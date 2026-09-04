# Quelaw 0.2: Evidence Review

Status: proposed next upgrade; planning only. Baseline: main after maintenance PR [#11](https://github.com/yamyr/Quelaw/pull/11) and annotation fix PR [#12](https://github.com/yamyr/Quelaw/pull/12), commit `5f14e0b8afb02d795607fe1d27cc1ac9d1ae4e76` (2026-09-03).

## Product outcome

A reviewer can select any citation occurrence, inspect the exact available evidence and its limits, decide whether to apply a correction, and export the same findings shown on screen. Every report identifies the draft and dataset version that produced it.

## Current foundation

The maintenance release provides Python 3.14, reproducible dependencies, offline verification, a Streamlit editor, annotated drafts, correction actions, quote hints, and exports. It preserves full subsection identifiers and uses contiguous normalized words for quote hints. The next milestone builds on these changes.

Remaining gaps are visible in the code: the sandbox loader accepts unvalidated dictionaries; source entries are paraphrases or placeholders; extraction collapses repeated references; corrections replace the first matching string; optional Claude results can attach the first retrieved source; Markdown omits detailed fields present in JSON. These gaps limit reviewability even when a demonstration produces the expected result.

## Scope and decisions

1. Preserve Python 3.14, Streamlit, uv, the offline default, and the existing four authority statuses. Use the already installed Pydantic v2 at external data boundaries. Keep computation separate from Streamlit state.
2. Validate the nine bundled source records and attach a stable dataset fingerprint. Record source identity, text fidelity, coverage, version information, reuse status, and available official URLs. Unknown information remains explicitly unknown. Never invent retrieval dates, licensing approval, or authoritative quotations for existing fixtures.
3. Preserve every citation occurrence in draft order. Report occurrence counts and distinct authority counts separately. Regex/Claude overlaps are deduplicated by validated span, never by neutral citation alone.
4. Bind corrections to the reviewed draft fingerprint and exact occurrence span. Reject stale or overlapping proposals. Applying one proposal changes only that occurrence; applying several works from right to left and requires a fresh check afterward.
5. Represent quotation evidence separately from authority matching. An exact phrase inside a paraphrase is evidence-limited. Incomplete text cannot prove that a quotation is absent from the full judgment. No state is named quote-authenticated or current-law-verified.
6. Bind optional Claude findings to a retrieved source identifier; titles, excerpts, and URLs come from the selected local record. Validate returned fields, reject unknown identifiers or unsupported quotations, and fall back to deterministic checking with an observable reason when the response cannot be used.
7. Make the app, JSON, and Markdown expose the same material findings, including review flags, source identity, dataset fingerprint, quotation limits, and correction proposals. Draft edits invalidate displayed results.
8. Add an offline evaluation corpus that separates extraction errors from verification errors, compares against a committed baseline, and fails CI on unreviewed changes. A domain reviewer must approve expected outcomes before claiming legal accuracy or widening coverage.

## Boundaries

This milestone delivers a reviewable local prototype. Official-source crawling, LawNet licensing, current-law/subsequent-treatment analysis, accounts, persistent private-draft storage, and a hosted service are separate decisions. The repository will continue to describe coverage honestly.

## Existing dependency security prerequisite

GitHub reports four open ChromaDB 1.5.9 advisories (two critical, two high) as of 2026-09-03: [pre-authentication code injection](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c), [authenticated code injection](https://github.com/advisories/GHSA-36p7-vc44-83pf), [cross-tenant authorization](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr), and [RBAC scoping](https://github.com/advisories/GHSA-xph7-9rjv-w5fr). The advisories list no patched version; [PyPI](https://pypi.org/project/chromadb/) lists 1.5.9 as the current release.

The described attack paths involve Chroma HTTP server endpoints or server authorization. Quelaw currently constructs an embedded `PersistentClient` in `quelaw/vectorstore.py`; it does not launch those HTTP endpoints or accept user-supplied embedding-model configuration. This limits exposure to the described paths, but does not clear the package alerts. Keep the alerts open. Before introducing a Chroma HTTP server or multi-tenant deployment, require a verified patched release or a reviewed alternative, update the lock/export, and repeat the relevant runtime/security checks. Do not represent current validation as a security certification.

## Release acceptance

- Three identical citations at different positions yield three independently selectable findings and one distinct authority.
- Correcting the second occurrence leaves the first and third byte-for-byte unchanged; stale and overlapping proposals cannot modify text.
- A subsection absent from the dataset remains unconfirmed even when the parent section is present.
- Missing provenance fields produce a validation error naming the file and field; a known placeholder remains usable only with explicit limits.
- Changing source text or provenance changes the dataset fingerprint; reordering object keys does not.
- Exact, negated, reordered, ambiguous, and missing nearby quotes cannot produce an authentication claim; limited source text produces a review flag.
- A mocked Claude response choosing candidate two produces candidate two's identity, excerpt, and URL; malformed or unknown candidates fall back visibly.
- UI, Markdown, and JSON preserve the same evidence and decisions for the same report fingerprint.
- Without an API key, index, or network connection after installation, demo and evaluation commands complete successfully.
- Keyboard and 390 px mobile review flows support finding selection, evidence reading, correction, recheck, and export without horizontal overflow.

## Delivery sequence

Source validation and dataset identity → occurrence-safe findings/corrections → quotation and retrieval evidence → review workspace/export parity → offline evaluation and release gate. Keep each change independently reviewable with a regression test and a working demonstration.

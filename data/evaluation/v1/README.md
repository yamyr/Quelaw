# Offline evaluation corpus v1

This is an engineering regression corpus for the untagged Quelaw 0.2.0 candidate. It is **not a legal accuracy benchmark**. All 48 cases carry `reviewer_status: legal_domain_review_pending` and `fixture_origin: synthetic`. Their expected outcomes were specified from the intended contracts and recorded source inventory, independently of pipeline output. Character offsets were located directly in the written drafts; no extractor or verifier generated the answer key.

Run from the repository root after installing locked dependencies:

```bash
uv run --locked python scripts/evaluate.py --dataset data/sandbox --cases data/evaluation/v1/cases.jsonl --baseline data/evaluation/v1/baseline.json
```

The command prints one JSON summary to stdout. Exit `0` means every material expectation and baseline identity matched; `1` means an expectation or baseline mismatch; `2` means invalid input or a filesystem error. `--dataset` selects the records actually used by every pipeline case. `--cases` defaults to this corpus; omitting `--baseline` permits exploratory evaluation while retaining strict material comparisons. The command never uses a vector index, embeddings, or Claude, even with credentials configured. The test suite installs network, retrieval, and API tripwires around a complete run.

## Coverage and limits

| Scenario kind | Cases | What it exercises |
|---|---:|---|
| `pipeline` | 33 | Real offline extraction, verification, correction proposals, and report identities across 37 expected citation occurrences |
| `quote_boundary` | 6 | Exact and punctuation-normalized phrases, negation, reordered/noncontiguous words, and missing text in an excerpt |
| `correction_boundary` | 2 | Applying only the second repeated occurrence and rejecting an edited draft |
| `claude_boundary` | 7 | The real typed verdict parser and evidence adapter using controlled payloads: source two selection, unknown source, wrong types, non-finite confidence, invented excerpt, and unsupported status |

Pipeline categories include exact case identifiers/names, explicitly planted absent citations, Singapore references outside this dataset, unsupported jurisdiction syntax, ordinary text, name/citation mismatch, parent and nested statutory provisions, rule abbreviations, repeated references, cross-type document order, paraphrase/absent quote limits, and ambiguous quote attribution. Unsupported syntax cases expect no detected occurrence and remain a stated coverage limitation.

The six quote cases use isolated, evaluator-authored nonlegal text. `text_kind: original` means verbatim fixture text; these records are still explicitly fictional, have `status: synthetic_fixture`, and cannot establish any legal proposition. They are embedded in the evaluation cases and never added to the sandbox inventory. This controlled distinction exercises original-text comparison semantics without upgrading the bundled paraphrases or placeholders.

The seven controlled Claude payload cases call no API. They validate adapter behavior, not Claude response quality. Live model evaluation, an independent legal answer key, additional jurisdictions, current-law status, and comprehensive authority coverage remain outside this corpus.

## What is compared

Each pipeline answer stores raw citation text, exact character offsets, citation type, case name/neutral citation, Act/section or order/rule fields, authority key, authority status, source ID, quote text and evidence state/source/matched text, manual-review flag, and correction replacement. The evaluator checks extraction and result offsets separately, finding IDs, report schema `2`, draft/dataset fingerprints, heuristic verifier metadata, absence of fallback in offline mode, full correction identity, and selected source provenance/title/official URL. A displayed excerpt must be nonempty literal available source text; source metadata must be absent when no source is selected. Quote evidence and review-required findings must have nonempty reasons. Free-form explanation wording and heuristic confidence scores are not treated as a legal answer key. The controlled Claude adapter cases additionally check that verdict status, review flag, confidence, and replacement survive adaptation correctly.

Extraction precision and recall use multiset matches of all parsed identity fields, preserving duplicate occurrences. Span accuracy counts matching identity, raw text, start, and end against expected occurrences. Thus correct authority recognition cannot conceal incorrect spans. Empty expected/detected sets score `1`; unexpected detections count as false positives. Authority confusion counts and quote-state outcomes are reported separately; controlled boundary cases are excluded from extraction and authority metrics. A wrong quote excerpt fails evaluation even if its quote-state count is unchanged.

`baseline.json` pins the source fingerprint, corpus byte hash, case count, and pending reviewer status. It contains no tolerated-failure list or aggregate-score threshold. Every material difference fails before considering any possible baseline update. A regression test changes one expected verified outcome to uncertain and checks that the command rejects the actual verification even alongside a baseline hash mismatch.

## Baseline maintenance

The initial baseline has 48 cases, 37 expected pipeline occurrences, no material mismatches, and extraction precision/recall/span accuracy of `1.0` on these engineered examples. These numbers report conformance to this answer key, not legal correctness or generalization.

When changing a case, review its draft, exact spans, source selection, and expectations individually. Explain whether a difference follows from source coverage or matching behavior. Run evaluation without a baseline to inspect all differences. After independent review of the material change, update the corpus hash, dataset fingerprint if applicable, and case count in `baseline.json`; then rerun the full command. Do not use implementation output to automatically rewrite expected verdicts. Keep the pending legal-review designation until a documented domain review actually occurs.

The bundled dataset has nine summaries: five paraphrases and four synthetic entries. It has no verified official URLs, retrieval dates, source versions, or reuse permissions. Its fingerprint for this baseline is `36e49d62e83e21e23c4e9b0671c6af70831c4e4092b1aa70ba7efa0cd44a7638`. Dataset matches and quote limitations must remain scoped to those records.

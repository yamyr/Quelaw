# Quelaw roadmap

Version **0.2.0 is an untagged release candidate** for reviewing citation occurrences against traceable, limited source evidence. The nine-record sandbox remains a demonstration dataset: five paraphrases and four synthetic entries, all summaries, with unknown retrieval/version details and unverified reuse status. See the [inventory](README.md#dataset-and-provenance) and [candidate notes](CHANGELOG.md).

## 0.2 candidate scope

- Singapore case, statute, and rule extraction from pasted text or `.txt`/`.docx` uploads, preserving repeated occurrences and full provision identifiers.
- Validated source provenance and a canonical dataset fingerprint recorded in reports and retrieval metadata.
- Occurrence-specific corrections bound to the reviewed draft hash and span, with stale/overlap rejection and a required recheck after edits.
- Separate authority and quotation findings, conservative treatment of paraphrases/incomplete text, and observable fallback when optional Claude evidence is invalid.
- A finding selector, occurrence context, provenance and review reasons, plus matching Markdown/JSON evidence using report schema `2`.
- Offline evaluation with at least 30 independently specified engineering fixtures, material expectation comparison, and separate extraction, verification, and quotation results.
- Python 3.14 and locked uv dependencies, dataset/evaluation checks, tests and demo checks, locked Ruff undefined-name lint, and requirements export drift checks in CI.

These capabilities support inspection and regression checking. They do not establish legal accuracy, comprehensive coverage, quotation authenticity, or current-law status. Evaluation legal expectations remain `legal_domain_review_pending`.

## Release gates still required

| Gate | Required evidence |
|---|---|
| Reproducible environment | Fresh locked install, dependency checks, dataset fingerprint, evaluation summary, tests, lint, and demo runs on supported Python. |
| Review workflow | Recorded upload → repeated occurrence selection → provenance inspection → one correction → recheck → matching Markdown/JSON downloads, including keyboard and 390 px browser checks. |
| Independent engineering review | Review of implementation, failure cases, evaluation expectations, and unresolved limitations; green CI for the candidate commit. |
| Dependency security | Dated recheck of all four ChromaDB advisories, kept visible while unresolved. Embedded use does not dismiss the alerts. |
| Release authorization | An explicit instruction after review and demonstration before creating a `v0.2.0` tag or deploying. |

The [release procedure](CONTRIBUTING.md#release-demonstration) defines the concrete demonstration. The [changelog](CHANGELOG.md) records candidate identity and limitations without claiming release approval.

## Next evidence and coverage work

- Obtain and record qualified legal domain review of evaluation expectations before making legal accuracy or coverage claims.
- Verify official source URLs, retrieval/version information, and reuse basis before replacing the current summary fixtures or expanding the inventory.
- Add independent cases from reviewed source material. Explain whether each changed expected result follows from new coverage or a changed matching rule.
- Resolve the four [ChromaDB advisories](CHANGELOG.md#unresolved-chromadb-advisories) through a verified patched version or reviewed alternative before any Chroma HTTP server or multi-tenant deployment; update the lock/export and repeat relevant runtime/security checks.

## Later work, subject to evidence and access

- Expand official-source coverage and assess licensed LawNet integration after provenance and reuse requirements are settled.
- Add URL availability checks with a distinction between a broken link and an unsupported authority.
- Investigate version, amendment, and subsequent-treatment evidence before making any claim about current legal status or overturned rulings.
- Evaluate a maintained hosted service after source quality, dependency security, and deployment behavior are established.

External search buttons provide manual follow-up links. They do not crawl official portals. The repository documents demo hosting options but does not advertise an existing hosted service; no tag or deployment is created by this milestone.

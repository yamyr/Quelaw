# Quelaw roadmap

The next milestone is a documented, evaluable citation-checking prototype with traceable sources and a repeatable release process. The current sandbox remains a demonstration dataset until its provenance and coverage are strengthened.

## Available now

- Singapore case, statute, and rule extraction from pasted text or `.txt`/`.docx` uploads.
- Deterministic sandbox matching and curated offline demo scenarios.
- Optional ChromaDB retrieval and Claude extraction/verification.
- Four controlled verification outcomes, summary counts, and overall risk.
- Annotated drafts, citation analysis cards, suggested transcription fixes, and external search links for manual review.
- Experimental nearby-quote match hints, plus Markdown and JSON report exports.
- A Python 3.14 environment managed with uv, reproducible dependencies, and offline pipeline and Streamlit interaction checks in CI.

These features are implemented. Their presence does not establish comprehensive legal coverage, quote authenticity, or current-law status.

## Next milestone

| Priority | Work | Completion evidence |
|---|---|---|
| 1. Source provenance | Define the supported sandbox scope; record source identity, official URL, retrieval date, version, and reuse basis. Clearly distinguish original text from paraphrases and fixtures. | A dataset inventory with traceable entries, explicit coverage limits, and checks for missing provenance. |
| 2. Evaluation | Create an independently reviewed evaluation set covering matched authorities, fabricated fixtures, out-of-scope references, citation mismatches, provisions, and quotes. Measure extraction and verification outcomes separately. | Versioned inputs and expected results, documented failure categories, and a repeatable offline evaluation report. |
| 3. Review reliability | Extend regression coverage for repeated references, edited drafts, correction spans, quote attribution, and LLM source selection. Make quote uncertainty and exported findings consistent with the reviewed evidence. | Regression cases for identified failures and documented behavior for ambiguous matches and incomplete source text. |
| 4. Release readiness | Exercise installation and demo flows on supported environments; review configuration, dependency updates, and deployment instructions. Record tested limitations and the dataset version used. | A tagged release with passing checks, a concise changelog, and a reproducible demonstration procedure. |

Changes in dataset coverage can legitimately change a result from **Not found in dataset** or **Requires manual review** to **Verified in dataset**. Evaluation updates should identify whether a changed outcome follows from new source coverage or a changed matching rule.

## Later work, subject to evidence and access

- Expand official-source coverage and assess licensed LawNet integration after provenance and reuse requirements are settled.
- Add URL availability checks with a clear distinction between a broken link and an unsupported authority.
- Investigate version, amendment, and subsequent-treatment evidence before making any claim about current legal status or overturned rulings.
- Evaluate a maintained hosted service once the prototype's source quality and deployment behavior are established.

External search buttons currently provide manual follow-up links. They do not crawl official portals. The repository documents how to deploy a demo but does not advertise an existing hosted service.

# Quelaw UI conventions

This document describes the current 0.2 interface in `app.py`,
`quelaw/review_ui.py`, `quelaw/annotator.py`, and `quelaw/schema.py`.
**Quelaw** is the canonical brand spelling. These conventions document the
implemented screen; they do not introduce a component library or a redesign.

## Rendering and layout

The app uses Streamlit's wide page layout and native typography, spacing, and
theme. Risk notices, finding details, source evidence, correction controls, and
exports use native Streamlit primitives. The annotated draft retains escaped
HTML with a fixed light palette; its colors do not automatically adapt to the
theme.

| Surface | Current primitives and order |
| --- | --- |
| Sidebar | Brand header and description; demo toggle; sandbox-document and indexed-chunk metrics; stale-index notice when needed; mode notice; rebuild action; dataset and deployment captions separated by dividers. |
| Draft input | Page title and introduction; scenario controls in demo mode or load/upload controls in normal mode; labelled “Legal draft” text area, 260 px high; primary “Run scenario” or “Check Draft” button. |
| Summary | Subheader; native risk notice; six metric columns for Occurrences, Distinct authorities, Verified, Not found, Uncertain, and Needs review; separate occurrence-review count and reliance caption. |
| Evidence review | “Select citation occurrence” selectbox; two equal native columns for the annotated draft and a bordered panel containing the selected occurrence's evidence; batch-correction action when proposals exist. |
| All findings | Compact numbered authority-status inventory with citation text, finding ID, and source ID; correction actions remain in Evidence review. |
| Report identity | Expander containing schema version, verifier mode, draft SHA-256, and dataset fingerprint; hashes use native code blocks. |
| Export and footer | Divider; two equal columns with full-width Markdown and JSON download buttons; final disclaimer below a divider. |

Use native `info`, `success`, `warning`, `error`, and spinner messages for
notices and progress. Overall risk uses `error` for High, `warning` for Medium,
`success` for Low, and `info` otherwise. These notices follow the Streamlit theme.
The metrics separate occurrence and distinct-authority totals from the four
authority outcomes. The review caption also accounts for quotation evidence
and other review flags.

## Selected occurrence and source evidence

The evidence panel shows the occurrence number, citation, authority status,
whole-percentage confidence, finding ID, citation type, character span,
explanation, context, and verifier. Review reasons are displayed as literal
plain text beneath their heading, so source or draft text is not interpreted
as Markdown or turned into remote content.

Available evidence includes the selected source title, source ID, excerpt,
text fidelity, coverage, and limitations. An “Open official source” button is
shown only when an official URL is available. Otherwise the panel states that
the official URL is unknown. Retrieval date, version, and reuse basis retain
explicit unknown values; reuse status remains `unverified` or `permitted`.
Missing selected evidence or provenance has a native notice.

Citation text, explanations, occurrence context, source titles and excerpts,
limitations, quotations, matched text, and replacement previews use plain text
rendering. Quotations have a separate assessment and reason. Available source
matches do not authenticate quotations. An official-source search action may
link to eLitigation or Singapore Statutes Online, independently of whether the
dataset supplies an official source URL.

## Annotation palette

Status labels and icons come from `quelaw/schema.py`. Only the annotation
marks use the fixed status colors below; the evidence panel uses native text.

| Status | Icon | Annotation background | Annotation text | Annotation border |
| --- | --- | --- | --- | --- |
| Verified in dataset | ✅ | `#d4efdf` | `#145a32` | `#27ae60` |
| Not found in dataset | ❌ | `#fadbd8` | `#78281f` | `#e74c3c` |
| Uncertain match | ⚠️ | `#fdebd0` | `#7e5109` | `#f39c12` |
| Requires manual review | 🔎 | `#d6eaf8` | `#1b4f72` | `#2980b9` |

An unrecognized annotation status uses background `#eaeded` and text
`#2c3e50`, with no status border. Its fallback icon is `•`, and the raw status
supplies the label.

## Annotated draft typography and spacing

| Element | Current style |
| --- | --- |
| Draft panel with results | White background; text `#1e293b`; `1.25rem 1.5rem` padding; 8 px radius; 1 px `#e2e8f0` border; shadow `0 1px 3px rgba(0,0,0,0.05)`. |
| Draft text with results | `Georgia, serif`; `1.02rem`; line-height `1.75`. |
| Citation mark | `2px 6px` padding; 4 px radius; weight 600; 1 px status border for known statuses. |
| Inline status label | Bracketed icon and label after the citation, at `0.8em`. |
| Annotation helper without results, or with a blank draft | Simple wrapper using `serif`, `1.05rem`, and line-height `1.7`; no styled panel. The report UI displays a no-authorities notice when there are no findings. |

Annotation escapes draft text and explanations, preserves line breaks with
`<br>`, and marks available citation spans in draft order. Overlapping spans are
skipped. Each mark has a browser `title` tooltip containing its status and
explanation. The selected finding's explanation is also readable in the evidence
panel, so the tooltip is supplemental.

## Draft, corrections, and report identity

The draft remains editable in normal and demo modes. Selecting a different
demo scenario loads its draft; ordinary reruns preserve edits. Normal mode
supports loading the demo draft or uploading `.txt` and `.docx` files. A loaded
upload is identified in session state so reruns do not overwrite later edits.
Checking an empty draft shows an error. Demo runs explicitly use the offline
heuristic verifier and require neither an API key nor an index.

Each correction has an expected-text and replacement preview. “Apply correction
to this occurrence” runs a callback that validates the saved proposal against
the current session draft at click time. “Apply all corrections” shows the
proposal count and applies the batch atomically. Both paths validate draft
identity and exact spans; stale or overlapping proposals produce a notice and
leave the draft unchanged. Successful application updates the editor, hides the
old report, and asks for another check.

The app loads and validates the source dataset on each rerun. A report appears
only while its saved draft matches the current editor text and its dataset
fingerprint matches the loaded sources. Draft edits or source changes hide the
old findings and exports and request a new check. An invalid dataset stops the
app with a validation error. A stale index displays a rebuild notice while
offline checks remain available; rebuilding is an explicit sidebar action.

The report identity and material findings are shared by the screen and both
user-triggered exports: `quelaw_report.md` and `quelaw_report.json`. Drafts,
uploads, and reports remain in session memory by default. The application does
not add a private-draft persistence path.

## Interaction and accessibility conventions

Keep occurrence selection, evidence inspection, correction, rechecking, and
downloads usable with native keyboard controls and at narrow phone widths.
The evidence columns stack in reading order on narrow screens. Long draft and
source text wrap; fingerprints use code blocks. Controls retain visible labels
and ordinary native focus behavior, with no decorative animation or external
assets.

Status meaning is expressed with words and, in annotations, icons as well as
color. Fixed annotation styling and hover tooltips coexist with Streamlit's
native controls. Workflow browser checks do not constitute a full framework
accessibility, contrast, assistive-technology, or performance audit.

## Reliance wording

“Verified in dataset” means a dataset match. “Not found in dataset” describes
dataset coverage. Neither establishes whether an authority is real, applicable,
or current law. Preserve the controlled status vocabulary and avoid calling a
case “fake” or “good law.”

Keep the dataset caveat visible: Micro-LawNet is a small controlled
proof-of-concept dataset with paraphrased or synthetic placeholder entries,
not authoritative legal text. Not-found results direct users to official
sources; uncertain and manual-review results ask users to read the source and
decide. The footer states that Quelaw supports verification, does not provide
legal advice or replace professional legal judgment, and requires manual review
of flagged items against official legal sources before use.

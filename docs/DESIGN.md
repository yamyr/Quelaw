# Quelaw UI conventions

This document records the existing interface in `app.py`,
`quelaw/annotator.py`, and `quelaw/schema.py`. **Quelaw** is the canonical brand
spelling. These conventions describe the current implementation; they do not
introduce a component library or a redesign.

## Rendering and layout

The app uses Streamlit's wide page layout and native typography, spacing, and
theme for most controls. Native Streamlit theming coexists with inline HTML
styles for the risk banner, citation status text, source excerpts, and annotated
draft. Those HTML colors are fixed and do not automatically adapt to the theme.

| Surface | Existing primitives and order |
| --- | --- |
| Sidebar | Brand header and description; demo toggle; document and index metrics; mode notice; rebuild action; dataset and deployment captions separated by dividers. |
| Draft input | Page title and introduction; scenario controls in demo mode or load/upload controls in normal mode; labelled text area, 260 px high; primary check/run button. |
| Summary | Subheader; risk banner; five equal metric columns for total, verified, not found, uncertain, and needs review; reliance caption. |
| Results | “📝 Annotated Draft” and “📋 Citation Analysis” tabs. Citation cards use bordered containers with a 3:2 heading/status split and two equal action columns. |
| Export and footer | Divider; two equal columns with full-width Markdown and JSON download buttons; final disclaimer below a divider. |

Use native `info`, `success`, `warning`, `error`, and spinner messages for the
existing notices and progress states. Buttons have text labels; emoji supplement
them. Source titles and URLs use captions, while explanations use normal body
text. Confidence is displayed as a whole percentage beside the citation status.

## Status and risk colors

Status labels and icons come from `quelaw/schema.py`. The card text color and
annotation palette are separate values in the current implementation.

| Status | Icon | Card text | Annotation background | Annotation text | Annotation border |
| --- | --- | --- | --- | --- | --- |
| Verified in dataset | ✅ | `#1e8449` | `#d4efdf` | `#145a32` | `#27ae60` |
| Not found in dataset | ❌ | `#c0392b` | `#fadbd8` | `#78281f` | `#e74c3c` |
| Uncertain match | ⚠️ | `#d68910` | `#fdebd0` | `#7e5109` | `#f39c12` |
| Requires manual review | 🔎 | `#2471a3` | `#d6eaf8` | `#1b4f72` | `#2980b9` |

The overall risk banner uses High `#c0392b`, Medium `#d68910`, Low `#1e8449`,
and Unknown `#566573`, with white text at weight 600. It has `0.75rem 1rem`
padding and an 8 px radius. Unrecognized card statuses also use `#566573`;
unrecognized annotation statuses use background `#eaeded` and text `#2c3e50`.
The fallback icon is `•`, and the raw status supplies the fallback label.

## Annotated draft typography and spacing

| Element | Existing style |
| --- | --- |
| Draft panel with results | White background; text `#1e293b`; `1.25rem 1.5rem` padding; 8 px radius; 1 px `#e2e8f0` border; shadow `0 1px 3px rgba(0,0,0,0.05)`. |
| Draft text with results | `Georgia, serif`; `1.02rem`; line-height `1.75`. |
| Citation mark | `2px 6px` padding; 4 px radius; weight 600; 1 px status border for known statuses. |
| Inline status label | Bracketed icon and label after the citation, at `0.8em`. |
| Draft without results, or blank draft | Simple wrapper using `serif`, `1.05rem`, and line-height `1.7`; no styled panel. |
| Card source excerpt | `0.85rem`; text `#444`; 3 px left border in the card status color; `0.6rem` left padding; `0.5rem` bottom margin. |

Annotation escapes draft text and explanations, preserves line breaks with
`<br>`, and marks available citation spans in draft order. Overlapping spans are
skipped. Each mark has a browser `title` tooltip containing its status and
explanation.

## Interaction and accessibility conventions

The draft remains editable in both normal and demo modes. Selecting a different
demo scenario loads its draft; ordinary reruns preserve edits. Checking an empty
draft shows an error. A report is displayed only while its saved draft matches
the current editor text, so edits require another check.

Suggested corrections are explicit user actions: per-citation Quick Fix or
Apply All Fixes. They update the draft and rerun the interface; the user checks
the revised draft again. Official-source search buttons and exports remain
separate actions. Quote hints appear as information or warning messages within
the relevant citation card, with an explicit reminder that sandbox matches
do not authenticate quotations.

Status meaning is expressed with words and icons as well as color. Explanations
are readable in Citation Analysis, so the annotation's hover tooltip is
supplemental. Native controls retain visible labels. Fixed HTML styling and
browser tooltips coexist with Streamlit behavior; this document does not assert
that contrast, keyboard access, or assistive-technology support has been audited.

## Reliance wording

“Verified in dataset” means a dataset match. “Not found in dataset” describes
dataset coverage. Neither establishes whether an authority is real, applicable,
or current law. Preserve the controlled status vocabulary and avoid calling a
case “fake” or “good law.”

Keep the interface's dataset caveat visible: Micro-LawNet is a small controlled
proof-of-concept dataset with paraphrased or placeholder entries, not
authoritative legal text. Not-found results direct users to official sources;
uncertain and manual-review results ask users to read the source and decide.
The footer states that Quelaw supports verification, does not provide legal
advice or replace professional legal judgment, and requires manual review of
flagged items against official legal sources before use.

## 0.2 evidence review workspace

The 0.2 screen preserves Streamlit's native controls and theme. It adds no
custom typography, palette, motion, JavaScript framework, or external assets.
The primary user is a reviewer comparing a draft occurrence with limited local
evidence; the same flow must remain usable by keyboard and on a narrow phone.

The summary separates **Occurrences** from **Distinct authorities**, with the
four existing authority counts beside them. A native risk notice states the
scope of available evidence. A separate count identifies occurrences needing
review, including quotations and fallback notices.

The **Evidence review** tab contains a labelled occurrence selectbox followed
by two native columns: annotated draft and a bordered evidence panel. On narrow
screens the columns stack in reading order. The selected occurrence shows its
exact span, context, authority status, source ID, fidelity and coverage,
limitations, official provenance (including explicit unknowns), quotation
assessment, review reasons, and correction preview. Long draft/source text
wraps; fingerprints use native code blocks. **All findings** provides a compact
status inventory without repeating correction actions.

A correction callback validates the saved proposal against the current session
draft at click time. Failure shows a review message and leaves the draft intact.
Successful application hides the old report and asks for a new check. All-fixes
shows the number of proposals and applies the validated batch atomically.
Changing the dataset fingerprint also hides the report. A stale index shows a
rebuild notice; deterministic offline checks remain available.

The evidence panel, status notice, correction preview and export controls are
reusable native primitives implemented in `quelaw/review_ui.py`. They use visible
labels, ordinary focus behavior and no decorative animation. Source text uses
plain text rendering. Existing escaped draft annotation is retained; its fixed
light palette is unchanged. Browser evidence will cover desktop, tablet and
390 px layouts, selector keyboard use, report invalidation, one-occurrence
correction and both downloads. This is a focused workflow validation, not a
claim of a full Streamlit framework accessibility or performance audit.

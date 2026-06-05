# QueLaw test memo — expected results

Test input: [`test_memo.txt`](test_memo.txt) / [`test_memo.docx`](test_memo.docx)

A deliberately mixed AI-style legal memo that exercises **every** verification
outcome. Run it through QueLaw (paste the `.txt`, or upload the `.docx`) and the
report should match the table below. Verified against the offline heuristic
engine on 2026-06-05.

## Expected per-citation results

| # | Authority cited | Type | Expected status | Why |
|---|---|---|---|---|
| 1 | Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency **[2007] SGCA 37** | case | ✅ Verified | Exact citation in sandbox |
| 2 | ACB v Thomson Medical Pte Ltd **[2016] SGCA 20** | case | ⚠️ Uncertain match | Real case name, **wrong year** (sandbox has [2017] SGCA 20) |
| 3 | RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd **[2007] SGCA 39** | case | ✅ Verified | Exact citation in sandbox |
| 4 | Lim Wei Ming v Oceanic Shipping Pte Ltd **[2024] SGHC 412** | case | ❌ Not found | Fabricated case — the planted hallucination |
| 5 | section **14** of the Civil Law Act | statute | ✅ Verified | Act + section both in sandbox |
| 6 | section **45** of the Civil Law Act | statute | 🔎 Requires review | Act in sandbox, but **section 45 not** confirmed |
| 7 | section **300** of the Penal Code | statute | ✅ Verified | Act + section both in sandbox |
| 8 | section **7** of the Maritime Conventions Act | statute | ❌ Not found | Act not in sandbox |
| 9 | **Order 9 Rule 6** of the Rules of Court | rule | ✅ Verified | Provision in sandbox |
| 10 | **Order 21 Rule 2** of the Rules of Court | rule | 🔎 Requires review | Rules of Court in sandbox, but this provision not confirmed |

## Expected summary

| Metric | Value |
|---|---|
| Total | 10 |
| Verified | 5 |
| Not found | 2 |
| Uncertain | 1 |
| Requires review | 2 |
| **Overall risk** | **High** (≥1 not found → possible hallucination) |

## What each outcome demonstrates

- **Verified** — the citation matches a trusted source exactly.
- **Uncertain match** (#2) — catches a *transcription error* in an otherwise real
  citation (wrong year), rather than crying "fake".
- **Requires review** (#6, #10) — the instrument exists but the specific
  section/provision couldn't be confirmed in the (small) sandbox.
- **Not found** (#4, #8) — no match at all; #4 is the key hallucination-detection
  case the tool exists to catch.

> Note: results reflect the proof-of-concept sandbox. With a wider dataset (or
> LawNet integration), #6/#8/#10 could move to verified — that's expected, and is
> why the wording stays conservative ("requires manual review", never "fake").

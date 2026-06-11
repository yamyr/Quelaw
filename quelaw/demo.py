"""Curated demo scenarios for live MVP demonstrations.

Demo mode runs the **offline heuristic** verifier (deterministic, no API key, no
vector index required), so every scenario below produces the same report on any
machine — exactly what you want when demoing live to judges.

Each scenario is self-contained: the draft text is inlined here rather than read
from disk, so the demo can't break because a data file moved. Each also carries
the expected per-citation outcome, which ``scripts/check_demo_scenarios.py`` and
``tests/test_demo.py`` assert so the demo never silently drifts.

Mentor steer (Noemie, 2026-06-11): lead the demo with the *fabricated-case* check
— that's the failure lawyers fear most and the one we can do well today. The
``HERO`` scenario is that headline; the others show we don't cry wolf and that we
flag-for-review rather than scream "fake".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .schema import NOT_FOUND, REQUIRES_REVIEW, UNCERTAIN, VERIFIED


@dataclass(frozen=True)
class Expectation:
    """An expected outcome for one citation, identified by a substring of it."""

    match: str  # substring that uniquely identifies the citation in the report
    status: str


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str  # shown in the picker
    tagline: str  # one-line description under the picker
    talking_point: str  # what to say to the room while it runs
    draft: str
    expected_risk: str
    expected: List[Expectation] = field(default_factory=list)


# --- 1. The headline: a fabricated authority hidden in a tidy memo ----------
HERO = Scenario(
    id="hallucinated_case",
    title="🎯 Hallucinated case (the headline check)",
    tagline="A tidy-looking memo with one invented authority buried inside.",
    talking_point=(
        "Everything here reads plausibly — but Lim Wei Ming v Oceanic Shipping "
        "doesn't exist. A fabricated case is the failure lawyers fear most, and "
        "it's exactly what QueLaw is built to catch. Watch it flag the fake while "
        "passing the two genuine authorities."
    ),
    draft="""MEMORANDUM — DUTY OF CARE (DRAFT PREPARED WITH AI ASSISTANCE)

1. The governing test for a duty of care in negligence in Singapore is the single
   two-stage test of proximity and policy laid down in Spandeck Engineering (S)
   Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37.

2. Counsel relies on Lim Wei Ming v Oceanic Shipping Pte Ltd [2024] SGHC 412 as
   having extended that duty of care to purely commercial relationships.

3. The statutory basis for the contribution claim is section 14 of the Civil Law
   Act.
""",
    expected_risk="High",
    expected=[
        Expectation("[2007] SGCA 37", VERIFIED),
        Expectation("[2024] SGHC 412", NOT_FOUND),
        Expectation("section 14", VERIFIED),
    ],
)


# --- 2. Don't cry wolf: a draft where everything is genuinely fine ----------
CLEAN = Scenario(
    id="clean_draft",
    title="✅ Clean draft (no issues)",
    tagline="Every authority is real and correctly cited — the tool should stay quiet.",
    talking_point=(
        "Just as important as catching fakes: not crying wolf. Every citation here "
        "checks out, so QueLaw returns Low risk and gets out of the lawyer's way. "
        "A checker that flags everything is a checker nobody trusts."
    ),
    draft="""MEMORANDUM — CONTRACT AND NEGLIGENCE (CLEAN DRAFT)

1. The duty of care test is the two-stage proximity-and-policy test in Spandeck
   Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37.

2. On the right to terminate for breach, the structured framework in RDC Concrete
   Pte Ltd v Sato Kogyo (S) Pte Ltd [2007] SGCA 39 applies.

3. The statutory basis for the contribution claim is section 14 of the Civil Law
   Act, and the relevant criminal provision is section 300 of the Penal Code.

4. Service is to be effected in accordance with Order 9 Rule 6 of the Rules of
   Court.
""",
    expected_risk="Low",
    expected=[
        Expectation("[2007] SGCA 37", VERIFIED),
        Expectation("[2007] SGCA 39", VERIFIED),
        Expectation("section 14", VERIFIED),
        Expectation("section 300", VERIFIED),
        Expectation("Order 9 Rule 6", VERIFIED),
    ],
)


# --- 3. The nuance judges love: a real case with a wrong year ---------------
WRONG_CITATION = Scenario(
    id="wrong_citation",
    title="⚠️ Right case, wrong citation",
    tagline="A real case cited with the wrong year — a transcription slip, not a fabrication.",
    talking_point=(
        "ACB v Thomson Medical is a real, leading case — but the year is wrong "
        "(it's [2017], not [2016]). QueLaw flags it as an uncertain match for "
        "review rather than screaming 'fake'. That careful wording is what earns a "
        "lawyer's trust: a wrong 'fake' label is as damaging as a missed one."
    ),
    draft="""MEMORANDUM — NOVEL HEADS OF DAMAGE (DRAFT)

1. The duty of care test remains that in Spandeck Engineering (S) Pte Ltd v
   Defence Science & Technology Agency [2007] SGCA 37.

2. On the recoverability of novel heads of damage, see ACB v Thomson Medical Pte
   Ltd [2016] SGCA 20.
""",
    expected_risk="Medium",
    expected=[
        Expectation("[2007] SGCA 37", VERIFIED),
        Expectation("[2016] SGCA 20", UNCERTAIN),
    ],
)


# --- 4. The full spread: every outcome on one screen ------------------------
# Draft text is the validated test memo (data/demo/test_memo.txt), inlined here so
# the scenario is self-contained. Expected outcomes mirror test_memo_expected.md.
MIXED = Scenario(
    id="mixed_memo",
    title="🧪 Mixed memo (every outcome)",
    tagline="Ten authorities exercising all four verification outcomes at once.",
    talking_point=(
        "The whole spread on one screen: verified, uncertain, requires-review and "
        "not-found — including the planted fake (Oceanic Shipping) and a statute "
        "the sandbox doesn't carry (Maritime Conventions Act). This is the slide "
        "that shows the verification model end to end."
    ),
    draft="""MEMORANDUM OF ADVICE

To:      Instructing Solicitors
From:    Chambers
Re:      Negligence and Contractual Claims — Preliminary Assessment

1. Duty of care. The governing test for the existence of a duty of care in
   negligence in Singapore remains the single two-stage test of proximity and
   policy articulated in Spandeck Engineering (S) Pte Ltd v Defence Science &
   Technology Agency [2007] SGCA 37. We are satisfied that the threshold of
   factual foreseeability is met on the present facts.

2. Novel heads of loss. As to the recoverability of novel heads of damage, we
   have considered ACB v Thomson Medical Pte Ltd [2016] SGCA 20, though counsel
   should note that the citation as drafted may require checking.

3. Termination. On the client's right to terminate the sub-contract, the
   structured framework in RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd [2007]
   SGCA 39 applies, and we consider the breach falls within the third situation
   identified there.

4. Recent authority. We would also draw attention to Lim Wei Ming v Oceanic
   Shipping Pte Ltd [2024] SGHC 412, which counsel advises extends the duty of
   care to purely commercial relationships in the shipping context.

5. Statutory framework. The statutory basis for the contribution claim is
   section 14 of the Civil Law Act, and we have separately considered section 45
   of the Civil Law Act in relation to assignment. The criminal exposure, if
   any, would arise under section 300 of the Penal Code. Counsel has also
   referred us to section 7 of the Maritime Conventions Act.

6. Procedure. Service should be effected in accordance with Order 9 Rule 6 of
   the Rules of Court; an application to strike out may be brought under Order 21
   Rule 2 of the Rules of Court.

This memorandum was prepared with the assistance of an AI drafting tool and must
be checked against primary sources before it is relied upon.
""",
    expected_risk="High",
    expected=[
        Expectation("[2007] SGCA 37", VERIFIED),
        Expectation("[2016] SGCA 20", UNCERTAIN),
        Expectation("[2007] SGCA 39", VERIFIED),
        Expectation("[2024] SGHC 412", NOT_FOUND),
        Expectation("section 14", VERIFIED),
        Expectation("section 45", REQUIRES_REVIEW),
        Expectation("section 300", VERIFIED),
        Expectation("Maritime Conventions Act", NOT_FOUND),
        Expectation("Order 9 Rule 6", VERIFIED),
        Expectation("Order 21 Rule 2", REQUIRES_REVIEW),
    ],
)


SCENARIOS: List[Scenario] = [HERO, CLEAN, WRONG_CITATION, MIXED]


def by_id(scenario_id: str) -> Scenario:
    for s in SCENARIOS:
        if s.id == scenario_id:
            return s
    raise KeyError(scenario_id)


def by_title(title: str) -> Scenario:
    for s in SCENARIOS:
        if s.title == title:
            return s
    raise KeyError(title)

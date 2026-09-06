"""Golden-path smoke test: run the pipeline over the demo memo and print results.

    uv run --locked python scripts/check_demo.py

Exercises extraction -> heuristic verification -> report end to end.
Always offline, even when a Claude API key is configured.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from quelaw.config import DEMO_DIR  # noqa: E402
from quelaw.pipeline import check_draft  # noqa: E402
from quelaw.schema import STATUS_LABEL  # noqa: E402


def main() -> None:
    draft = (DEMO_DIR / "golden_path.txt").read_text(encoding="utf-8")
    print("Verification: offline heuristic (Claude disabled)\n")

    report, citations = check_draft(draft, use_llm=False)

    print(f"Extracted {len(citations)} authorities:\n")
    for r in report.results:
        label = STATUS_LABEL.get(r.status, r.status)
        print(f"  [{label:<22}] ({r.confidence:.2f}) {r.citation}")
        print(f"       {r.explanation}")
        if r.source_title:
            print(f"       source: {r.source_title}")
        print()

    s = report.summary
    print(
        f"Summary: total={s['total']} verified={s['verified']} "
        f"not_found={s['not_found']} uncertain={s['uncertain']} "
        f"requires_review={s['requires_review']}"
    )
    print(f"Overall risk: {report.risk_level} — {report.risk_detail}")


if __name__ == "__main__":
    main()

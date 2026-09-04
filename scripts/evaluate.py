"""Run with: uv run --locked python scripts/evaluate.py --dataset data/sandbox."""

import getopt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from quelaw.evaluation import EvaluationInputError, evaluate
from quelaw.provenance import DatasetValidationError


def main() -> int:
    try:
        options, extra = getopt.getopt(sys.argv[1:], "", ["dataset=", "cases=", "baseline="])
        if extra:
            raise EvaluationInputError("unexpected positional arguments")
        paths = {name: Path(value) for name, value in options}
        summary = evaluate(paths.get("--dataset", Path("data/sandbox")),
                           paths.get("--cases", Path("data/evaluation/v1/cases.jsonl")),
                           paths.get("--baseline"))
    except (getopt.GetoptError, OSError, ValidationError, DatasetValidationError, EvaluationInputError) as error:
        print(json.dumps({"passed": False, "error": str(error)}))
        return 2
    print(summary.model_dump_json(indent=2))
    return 0 if summary.passed else 1


if __name__ == "__main__":
    sys.exit(main())

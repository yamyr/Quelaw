from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from quelaw import sandbox
from quelaw.config import SANDBOX_DIR

type JsonObject = dict[str, JsonValue]
JSON_OBJECT: Final = TypeAdapter(JsonObject)
ROOT: Final = Path(__file__).resolve().parents[1]


def source_fixture(document_id: str = "sample") -> JsonObject:
    return {
        "document_id": document_id, "title": "Fixture authority",
        "source_type": "case", "citation": "[2020] SGCA 1", "court": "Fixture court",
        "date": "2020-01-01", "source_url": "placeholder", "status": "sample",
        "text": "Synthetic fixture source text.",
        "provenance": {
            "text_kind": "synthetic", "coverage": "summary", "official_url": None,
            "retrieved_on": None, "version_label": None, "reuse_status": "unverified",
            "reuse_basis": None, "limitations": ["Synthetic test fixture."],
        },
    }


def write_source(root: Path, payload: JsonObject, name: str = "source.json") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def provenance_fixture(payload: JsonObject) -> JsonObject:
    return JSON_OBJECT.validate_python(payload["provenance"])


def rewrite_json_keys_in_reverse_order(root: Path) -> None:
    for path in root.rglob("*.json"):
        payload = JSON_OBJECT.validate_json(path.read_text(encoding="utf-8"))
        payload["provenance"] = dict(reversed(provenance_fixture(payload).items()))
        path.write_text(json.dumps(dict(reversed(payload.items()))), encoding="utf-8")


def change_source_text(root: Path, document_id: str, text: str) -> None:
    for path in root.rglob("*.json"):
        payload = JSON_OBJECT.validate_json(path.read_text(encoding="utf-8"))
        if payload["document_id"] == document_id:
            payload["text"] = text
            path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("field", [
    "text_kind", "coverage", "official_url", "retrieved_on", "version_label",
    "reuse_status", "reuse_basis", "limitations",
])
def test_missing_provenance_key_names_file_and_field(tmp_path: Path, field: str) -> None:
    # Given a required provenance key is absent, including nullable keys.
    payload = source_fixture()
    provenance = provenance_fixture(payload)
    del provenance[field]
    payload["provenance"] = provenance
    path = write_source(tmp_path, payload)
    # When the dataset is loaded, then the error identifies the input and field.
    with pytest.raises(ValueError, match=rf"{path.name}.*provenance\.{field}"):
        sandbox.load_dataset(tmp_path)


def test_duplicate_id_names_both_files(tmp_path: Path) -> None:
    # Given two records claim the same identity.
    write_source(tmp_path, source_fixture(), "first.json")
    write_source(tmp_path, source_fixture(), "second.json")
    # When loading, then both files and the offending key are identified.
    with pytest.raises(ValueError, match=r"second.json.*document_id.*first.json"):
        sandbox.load_dataset(tmp_path)


def test_placeholder_requires_explicit_limitations(tmp_path: Path) -> None:
    # Given a synthetic summary has a placeholder URL and no explicit limits.
    payload = source_fixture()
    provenance = provenance_fixture(payload)
    provenance["limitations"] = []
    payload["provenance"] = provenance
    write_source(tmp_path, payload)
    # When loading, then the error names the source file and limitations field.
    with pytest.raises(ValueError, match=r"source.json.*provenance\.limitations"):
        sandbox.load_dataset(tmp_path)


@pytest.mark.parametrize("basis", [None, "", "   "])
def test_permitted_reuse_requires_basis(tmp_path: Path, basis: str | None) -> None:
    # Given a permission claim lacks a usable basis.
    payload = source_fixture()
    provenance = provenance_fixture(payload)
    provenance.update(reuse_status="permitted", reuse_basis=basis)
    payload["provenance"] = provenance
    write_source(tmp_path, payload)
    # When loading, then the contradiction is rejected at the field boundary.
    with pytest.raises(ValueError, match=r"source.json.*provenance.reuse_basis"):
        sandbox.load_dataset(tmp_path)


def test_fingerprint_ignores_json_key_order(tmp_path: Path) -> None:
    # Given equivalent source files with reordered JSON object keys.
    write_source(tmp_path, source_fixture())
    first = sandbox.load_dataset(tmp_path)
    rewrite_json_keys_in_reverse_order(tmp_path)
    # When loading again, then identity remains stable.
    assert sandbox.load_dataset(tmp_path).fingerprint == first.fingerprint


def test_fingerprint_changes_with_source_text(tmp_path: Path) -> None:
    # Given source text changes after a dataset was identified.
    write_source(tmp_path, source_fixture())
    first = sandbox.load_dataset(tmp_path)
    change_source_text(tmp_path, "sample", "Changed fixture text")
    # When loading again, then the new evidence has a new identity.
    assert sandbox.load_dataset(tmp_path).fingerprint != first.fingerprint


def test_fingerprint_changes_with_provenance(tmp_path: Path) -> None:
    # Given the evidence limitations change without changing source text.
    payload = source_fixture()
    write_source(tmp_path, payload)
    first = sandbox.load_dataset(tmp_path)
    provenance = provenance_fixture(payload)
    provenance["limitations"] = ["Additional limitation."]
    payload["provenance"] = provenance
    write_source(tmp_path, payload)
    # When loading again, then provenance contributes to the identity.
    assert sandbox.load_dataset(tmp_path).fingerprint != first.fingerprint


def test_fingerprint_ignores_record_file_order(tmp_path: Path) -> None:
    # Given the same records are stored under differently ordered file names.
    write_source(tmp_path / "one", source_fixture("alpha"), "a.json")
    write_source(tmp_path / "one", source_fixture("beta"), "b.json")
    write_source(tmp_path / "two", source_fixture("alpha"), "z.json")
    write_source(tmp_path / "two", source_fixture("beta"), "a.json")
    first = sandbox.load_dataset(tmp_path / "one")
    # When loading the reordered inventory, then paths do not affect identity.
    assert sandbox.load_dataset(tmp_path / "two").fingerprint == first.fingerprint


@pytest.mark.parametrize("field,value", [("document_id", 10), ("text", True), ("unexpected", "x")])
def test_invalid_record_types_are_not_coerced(tmp_path: Path, field: str, value: JsonValue) -> None:
    # Given malformed source fields or an unrecognized key.
    payload = source_fixture()
    payload[field] = value
    write_source(tmp_path, payload)
    # When loading, then the boundary rejects the field.
    with pytest.raises(ValueError, match=rf"source.json.*{field}"):
        sandbox.load_dataset(tmp_path)


def test_source_models_are_frozen(tmp_path: Path) -> None:
    # Given a parsed record.
    write_source(tmp_path, source_fixture())
    record = sandbox.load_dataset(tmp_path).records[0]
    # When assignment is attempted, then validated evidence cannot mutate.
    with pytest.raises(ValidationError, match="frozen"):
        record.text = "Changed without validation"


def test_bundled_inventory_keeps_unknown_provenance_unknown() -> None:
    # Given the nine original sandbox entries.
    dataset = sandbox.load_dataset(SANDBOX_DIR)
    # Then source limitations are explicit and no placeholder becomes official.
    assert len(dataset.records) == 9
    assert all(record.provenance.official_url is None for record in dataset.records)
    assert all(record.provenance.retrieved_on is None for record in dataset.records)
    assert all(record.provenance.version_label is None for record in dataset.records)
    assert all(record.provenance.reuse_status == "unverified" for record in dataset.records)
    assert all(record.provenance.limitations for record in dataset.records)
    assert {record.provenance.text_kind for record in dataset.records} == {"paraphrase", "synthetic"}


def test_legacy_adapter_keeps_strings_and_file_metadata() -> None:
    # Given callers still consume dictionaries.
    documents = sandbox.load_documents()
    # Then source strings and input file paths remain available.
    assert len(documents) == 9
    assert all(Path(doc["_path"]).is_file() for doc in documents)
    assert all("placeholder" in doc["source_url"] for doc in documents)


def test_legacy_adapter_keeps_explicit_unknown_provenance() -> None:
    # Given callers inspect provenance through the dictionary adapter.
    documents = sandbox.load_documents()
    # Then unknown values remain present rather than becoming missing fields.
    assert all("official_url" in doc["provenance"] for doc in documents)
    assert all(doc["provenance"]["official_url"] is None for doc in documents)


def test_inventory_cli_prints_identity_and_counts() -> None:
    # Given the inventory command uses the installed project interpreter.
    result = subprocess.run(
        [sys.executable, "scripts/check_dataset.py"], cwd=ROOT,
        text=True, capture_output=True, check=False,
    )
    # Then a successful check emits the dataset identity and structured counts.
    assert result.returncode == 0, result.stderr
    payload = JSON_OBJECT.validate_json(result.stdout)
    assert payload["records"] == 9
    assert payload["fingerprint"] == sandbox.load_dataset(SANDBOX_DIR).fingerprint
    assert payload["text_kind"] == {"paraphrase": 5, "synthetic": 4}
    assert payload["coverage"] == {"summary": 9}


def test_inventory_cli_exits_nonzero_for_invalid_input(tmp_path: Path) -> None:
    # Given a malformed source passed to the real inventory command.
    payload = source_fixture()
    del payload["provenance"]
    write_source(tmp_path, payload)
    # When run, then it exits with a file-specific validation error.
    result = subprocess.run(
        [sys.executable, "scripts/check_dataset.py", "--dataset", str(tmp_path)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert result.returncode != 0
    assert "source.json" in result.stderr
    assert "provenance" in result.stderr

"""Validated source evidence; unknown provenance is never inferred from metadata."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticCustomError

type TextKind = Literal["original", "paraphrase", "synthetic"]
type Coverage = Literal["complete", "excerpt", "summary"]
type SourceType = Literal["case", "statute", "rule"]
type ReuseStatus = Literal["unverified", "permitted"]
type NonEmptyText = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Provenance(BaseModel):
    """All provenance keys are required; nullable values explicitly mean unknown."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    text_kind: TextKind
    coverage: Coverage
    official_url: HttpUrl | None
    retrieved_on: date | None
    version_label: NonEmptyText | None
    reuse_status: ReuseStatus
    reuse_basis: NonEmptyText | None
    limitations: tuple[NonEmptyText, ...] = Field(min_length=1)

    @field_validator("reuse_basis")
    @classmethod
    def require_permission_basis(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("reuse_status") == "permitted" and value is None:
            raise PydanticCustomError("reuse_basis_required", "permitted reuse requires a reuse_basis")
        return value


class SourceRecord(BaseModel):
    """A source entry whose legacy metadata makes no official-provenance claim."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    document_id: NonEmptyText
    title: NonEmptyText
    source_type: SourceType
    source_url: str
    status: NonEmptyText
    text: NonEmptyText
    provenance: Provenance
    citation: NonEmptyText | None = None
    court: NonEmptyText | None = None
    date: str | None = None
    version_date: str | None = None
    section: NonEmptyText | None = None
    provision: NonEmptyText | None = None
    order: NonEmptyText | None = None
    rule: NonEmptyText | None = None


@dataclass(frozen=True, slots=True)
class Dataset:
    records: tuple[SourceRecord, ...]
    fingerprint: str


class DatasetValidationError(ValueError):
    """A file-specific boundary error usable by CLI and application callers."""

    path: Path
    detail: str

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"{path}: {detail}")


def load_dataset(root: Path) -> Dataset:
    """Parse local JSON once and hash canonical records independently of paths."""
    if not root.is_dir():
        raise DatasetValidationError(root, "dataset directory does not exist")
    records: list[SourceRecord] = []
    paths_by_id: dict[str, Path] = {}
    for path in sorted(root.rglob("*.json")):
        try:
            record = SourceRecord.model_validate_json(path.read_bytes())
        except OSError as error:
            raise DatasetValidationError(path, str(error)) from error
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc']) or 'record'}: {item['msg']}"
                for item in error.errors(include_url=False, include_input=False)
            )
            raise DatasetValidationError(path, details) from error
        if record.document_id in paths_by_id:
            raise DatasetValidationError(
                path, f"document_id {record.document_id!r} duplicates {paths_by_id[record.document_id]}",
            )
        paths_by_id[record.document_id] = path
        records.append(record)
    payload = json.dumps(
        [record.model_dump(mode="json") for record in sorted(records, key=lambda record: record.document_id)],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return Dataset(records=tuple(records), fingerprint=hashlib.sha256(payload).hexdigest())

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from .provenance import SourceRecord

type AuthorityStatus = Literal[
    "verified", "not_found_in_dataset", "uncertain_match", "requires_manual_review",
]
type QuoteStatus = Literal[
    "match_in_available_text", "not_found_in_available_text",
    "evidence_limited", "ambiguous_attribution",
]


class EvaluationModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class ExpectedQuote(EvaluationModel):
    status: QuoteStatus
    source_id: str | None
    matched_text: str | None


class ExpectedOccurrence(EvaluationModel):
    raw_text: str
    type: Literal["case", "statute", "rule"]
    case_name: str | None
    citation: str | None
    act: str | None
    section: str | None
    order: str | None
    rule: str | None
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    authority_key: str
    status: AuthorityStatus
    source_id: str | None
    quote_text: str | None
    quote_evidence: ExpectedQuote | None
    manual_review_required: bool
    correction_replacement: str | None


class CaseMetadata(EvaluationModel):
    id: str
    draft: str
    failure_category: str
    reviewer_status: Literal["legal_domain_review_pending"]
    fixture_origin: Literal["synthetic"]
    rationale: str


class PipelineCase(CaseMetadata):
    kind: Literal["pipeline"]
    expected: tuple[ExpectedOccurrence, ...]


class QuoteCase(CaseMetadata):
    kind: Literal["quote_boundary"]
    quote: str
    source: SourceRecord
    expected: ExpectedQuote


class CorrectionCase(CaseMetadata):
    kind: Literal["correction_boundary"]
    start_char: int
    end_char: int
    expected_text: str
    replacement: str
    edited_draft: str
    expected: Literal["stale_rejected", "applied"]
    expected_draft: str | None


class ClaudeCase(CaseMetadata):
    kind: Literal["claude_boundary"]
    candidates: tuple[SourceRecord, ...]
    payload: str
    expected: Literal["rejected", "accepted"]
    expected_source_id: str | None


type EvaluationCase = PipelineCase | QuoteCase | CorrectionCase | ClaudeCase
CASE_ADAPTER = TypeAdapter(Annotated[EvaluationCase, Field(discriminator="kind")])


class Baseline(EvaluationModel):
    schema_version: Literal[1]
    dataset_fingerprint: str
    corpus_sha256: str
    case_count: int = Field(ge=30)
    reviewer_status: Literal["legal_domain_review_pending"]


class Mismatch(EvaluationModel):
    case_id: str
    field: str
    expected: JsonValue
    actual: JsonValue


class ExtractionMetrics(EvaluationModel):
    true_positive: int
    false_positive: int
    false_negative: int
    exact_spans: int
    precision: float
    recall: float
    span_accuracy: float


class EvaluationSummary(EvaluationModel):
    schema_version: Literal[1] = 1
    report_schema_version: Literal[2] = 2
    dataset_fingerprint: str
    corpus_sha256: str
    reviewer_status: Literal["legal_domain_review_pending"] = "legal_domain_review_pending"
    cases_run: int
    pipeline_cases_run: int
    boundary_cases_run: int
    extraction: ExtractionMetrics
    authority_confusion: dict[str, dict[str, int]]
    quote_outcomes: dict[str, dict[str, int]]
    mismatches: tuple[Mismatch, ...]
    passed: bool

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class JobMeta(_FlexibleModel):
    pipeline_version: str | None = None
    run_id: str | None = None
    created_at_utc: str | None = None
    source_type: str | None = None
    status: str | None = None


class SourceBundle(_FlexibleModel):
    platform: str | None = None
    author_handle: str | None = None
    author_display_name: str | None = None
    post_ids: list[str] = Field(default_factory=list)
    post_urls: list[str] = Field(default_factory=list)
    timestamps_utc: list[str] = Field(default_factory=list)
    language: str | None = None


class OCRTextItem(_FlexibleModel):
    image_id: str | None = None
    text: str | None = None
    quality: str | None = None


class ImageDescriptionItem(_FlexibleModel):
    image_id: str | None = None
    observed_visual_elements: list[str] = Field(default_factory=list)
    chart_timeframe: str | None = None
    instrument_hint: str | None = None
    confidence: float | None = None


class RawCapture(_FlexibleModel):
    text_exact: list[str] = Field(default_factory=list)
    ocr_text: list[OCRTextItem] = Field(default_factory=list)
    image_descriptions: list[ImageDescriptionItem] = Field(default_factory=list)


class EvidenceAwareItem(_FlexibleModel):
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float | None = None


SemanticStatus = Literal["observed", "inferred", "uncertain"]
CandidateStatus = Literal["candidate"]
DefinitionType = Literal["author_meaning", "operational_candidate", "heuristic", "warning"]


class TermDetected(EvidenceAwareItem):
    term: str
    normalized_term: str | None = None
    category: str | None = None
    status: SemanticStatus | None = None


class DefinitionCandidate(EvidenceAwareItem):
    term: str
    definition_text: str
    definition_type: DefinitionType | str
    status: SemanticStatus | None = None


class RelationCandidate(EvidenceAwareItem):
    subject: str
    relation: str
    object: str
    status: SemanticStatus | None = None


class VariantCandidate(EvidenceAwareItem):
    parent_term: str
    variant_name: str
    description: str
    status: SemanticStatus | None = None


class ContradictionOrAmbiguity(_FlexibleModel):
    topic: str | None = None
    description: str | None = None
    why_ambiguous: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class KnowledgeExtract(_FlexibleModel):
    terms_detected: list[TermDetected] = Field(default_factory=list)
    definitions_candidate: list[DefinitionCandidate] = Field(default_factory=list)
    relations_candidate: list[RelationCandidate] = Field(default_factory=list)
    variants_candidate: list[VariantCandidate] = Field(default_factory=list)
    contradictions_or_ambiguities: list[ContradictionOrAmbiguity] = Field(default_factory=list)


class LabeledContextItem(_FlexibleModel):
    label: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class TradingContextExtract(_FlexibleModel):
    htf_elements: list[LabeledContextItem] = Field(default_factory=list)
    ltf_elements: list[LabeledContextItem] = Field(default_factory=list)
    time_windows_mentioned: list[LabeledContextItem] = Field(default_factory=list)
    poi_elements: list[LabeledContextItem] = Field(default_factory=list)
    liquidity_elements: list[LabeledContextItem] = Field(default_factory=list)
    execution_elements: list[LabeledContextItem] = Field(default_factory=list)
    invalidation_elements: list[LabeledContextItem] = Field(default_factory=list)
    outcome_elements: list[LabeledContextItem] = Field(default_factory=list)


class PotentialEvent(_FlexibleModel):
    name: str
    description: str | None = None
    source_terms: list[str] = Field(default_factory=list)
    status: CandidateStatus | str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PotentialQuestion(_FlexibleModel):
    question_key_candidate: str
    question_text: str
    scope: str | None = None
    trigger_terms: list[str] = Field(default_factory=list)
    status: CandidateStatus | str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PotentialPlayCandidate(_FlexibleModel):
    family: str | None = None
    name: str
    description: str | None = None
    status: CandidateStatus | str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class ContextorMappingCandidates(_FlexibleModel):
    potential_events: list[PotentialEvent] = Field(default_factory=list)
    potential_questions: list[PotentialQuestion] = Field(default_factory=list)
    potential_play_candidates: list[PotentialPlayCandidate] = Field(default_factory=list)


class QualityControl(_FlexibleModel):
    missing_data: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    possible_hallucination_risks: list[str] = Field(default_factory=list)
    needs_human_review: bool | None = None


class ProvenanceEntry(_FlexibleModel):
    ref_id: str
    type: str | None = None
    source_post_id: str | None = None
    image_id: str | None = None
    excerpt: str | None = None


class CanonicalKnowledgeRecord(_FlexibleModel):
    job_meta: JobMeta = Field(default_factory=JobMeta)
    source_bundle: SourceBundle = Field(default_factory=SourceBundle)
    raw_capture: RawCapture = Field(default_factory=RawCapture)
    knowledge_extract: KnowledgeExtract = Field(default_factory=KnowledgeExtract)
    trading_context_extract: TradingContextExtract = Field(default_factory=TradingContextExtract)
    contextor_mapping_candidates: ContextorMappingCandidates = Field(default_factory=ContextorMappingCandidates)
    quality_control: QualityControl = Field(default_factory=QualityControl)
    provenance_index: list[ProvenanceEntry] = Field(default_factory=list)


def canonical_knowledge_record_json_schema() -> dict[str, Any]:
    return CanonicalKnowledgeRecord.model_json_schema()


def validate_canonical_knowledge_contract(record: dict) -> dict[str, Any]:
    try:
        model = CanonicalKnowledgeRecord.model_validate(record)
    except ValidationError as exc:
        return {
            "ok": False,
            "errors": [
                {
                    "loc": [str(part) for part in err.get("loc", ())],
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()
            ],
        }
    return {"ok": True, "errors": [], "normalized": model.model_dump(mode="python")}

from x_legal_stuff_webscrapper.knowledge_schema import (
    canonical_knowledge_record_json_schema,
    validate_canonical_knowledge_contract,
)


def _canonical_record() -> dict:
    return {
        "job_meta": {"status": "ok"},
        "source_bundle": {"post_ids": ["p1"]},
        "raw_capture": {"text_exact": ["hello"], "ocr_text": [], "image_descriptions": []},
        "knowledge_extract": {
            "terms_detected": [
                {
                    "term": "IFVG",
                    "normalized_term": "ifvg",
                    "category": "concept",
                    "status": "observed",
                    "evidence_refs": ["ocr:img1"],
                    "confidence": None,
                }
            ],
            "definitions_candidate": [],
            "relations_candidate": [],
            "variants_candidate": [],
            "contradictions_or_ambiguities": [],
        },
        "trading_context_extract": {
            "htf_elements": [],
            "ltf_elements": [],
            "time_windows_mentioned": [],
            "poi_elements": [],
            "liquidity_elements": [],
            "execution_elements": [],
            "invalidation_elements": [],
            "outcome_elements": [],
        },
        "contextor_mapping_candidates": {
            "potential_events": [],
            "potential_questions": [],
            "potential_play_candidates": [],
        },
        "quality_control": {
            "missing_data": [],
            "uncertainties": [],
            "possible_hallucination_risks": [],
            "needs_human_review": True,
        },
        "provenance_index": [{"ref_id": "ocr:img1"}],
    }


def test_schema_export_returns_json_schema() -> None:
    schema = canonical_knowledge_record_json_schema()
    assert "properties" in schema
    assert "knowledge_extract" in schema["properties"]


def test_contract_validation_accepts_minimal_canonical_record() -> None:
    result = validate_canonical_knowledge_contract(_canonical_record())
    assert result["ok"] is True
    assert result["errors"] == []


def test_contract_validation_rejects_wrong_type() -> None:
    rec = _canonical_record()
    rec["provenance_index"] = {}
    result = validate_canonical_knowledge_contract(rec)
    assert result["ok"] is False
    assert result["errors"]

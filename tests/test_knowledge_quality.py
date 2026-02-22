from x_legal_stuff_webscrapper.knowledge_quality import (
    canonicalize_knowledge_record,
    run_quality_gates_for_knowledge_records,
    validate_canonical_knowledge_record,
)


def _sample_record_with_aliases() -> dict:
    return {
        "job_meta": {"status": "partial"},
        "source_bundle": {"post_ids": ["p1"]},
        "raw_capture": {"image_descriptions": [{"image_id": "img1", "observed_visual_elements": [], "chart_timeframe": None, "instrument_hint": None, "confidence": 0.0}]},
        "knowledge_extract": {
            "terms_detected": [
                {
                    "term": "IFVG",
                    "interpretation_status": "observed",
                    "definition": "Inversion fair value gap",
                    "evidence_refs": ["ocr:img1"],
                }
            ],
            "definitions_candidate": [{"concept": "FVG", "definition": "Fair value gap"}],
            "relations_candidate": [{"from": "IFVG", "property": "variant_of", "to": "FVG"}],
            "variants_candidate": [],
            "contradictions_or_ambiguities": [],
        },
        "trading_context_extract": {"htf_elements": ["PDH"], "ltf_elements": [], "time_windows_mentioned": [], "poi_elements": [], "liquidity_elements": [], "execution_elements": [], "invalidation_elements": [], "outcome_elements": []},
        "contextor_mapping_candidates": {
            "potential_events": [{"event": "Stop hunt then IFVG"}],
            "potential_questions": ["How confirm IFVG?"],
            "potential_play_candidates": [{"play": "IFVG retest short"}],
        },
        "quality_control": {"missing_data": [], "uncertainties": [], "possible_hallucination_risks": [], "needs_human_review": True},
        "provenance_index": [{"ref_id": "post:p1:text"}, {"ref_id": "ocr:img1"}],
    }


def test_canonicalizer_maps_aliases_and_question_strings() -> None:
    result = canonicalize_knowledge_record(_sample_record_with_aliases())
    record = result["canonical_record"]

    term = record["knowledge_extract"]["terms_detected"][0]
    assert term["status"] == "observed"
    assert term["normalized_term"] == "ifvg"
    assert term["category"] == "concept"

    defs = record["knowledge_extract"]["definitions_candidate"]
    assert any(d.get("term") == "FVG" and "definition_text" in d for d in defs)
    assert any(d.get("term") == "IFVG" and d.get("definition_text") == "Inversion fair value gap" for d in defs)

    rel = record["knowledge_extract"]["relations_candidate"][0]
    assert rel["subject"] == "IFVG"
    assert rel["relation"] == "variant_of"
    assert rel["object"] == "FVG"

    q = record["contextor_mapping_candidates"]["potential_questions"][0]
    assert isinstance(q, dict)
    assert q["status"] == "candidate"
    assert q["scope"] == "unknown"

    assert record["trading_context_extract"]["htf_elements"][0]["label"] == "PDH"


def test_validator_detects_partial_without_missing_data_warning() -> None:
    canon = canonicalize_knowledge_record(_sample_record_with_aliases())["canonical_record"]
    validation = validate_canonical_knowledge_record(canon)
    codes = {w["code"] for w in validation["warnings"]}
    assert "partial_without_missing_data_reason" in codes
    assert validation["metrics"]["broken_refs_count"] == 0


def test_term_status_fallback_prefers_uncertain_when_definition_present() -> None:
    rec = _sample_record_with_aliases()
    term = rec["knowledge_extract"]["terms_detected"][0]
    term.pop("interpretation_status", None)
    result = canonicalize_knowledge_record(rec)["canonical_record"]
    assert result["knowledge_extract"]["terms_detected"][0]["status"] == "uncertain"


def test_run_quality_gates_reports_broken_refs() -> None:
    rec = _sample_record_with_aliases()
    rec["knowledge_extract"]["relations_candidate"][0]["evidence_refs"] = ["missing:ref"]
    result = run_quality_gates_for_knowledge_records([rec])
    assert result["qa_report"]["quality_gate_metrics"]["broken_refs_count"] == 1

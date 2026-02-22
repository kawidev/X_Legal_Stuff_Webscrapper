from x_legal_stuff_webscrapper.knowledge_library_export import export_knowledge_library_streams


def _canonical_record() -> dict:
    return {
        "job_meta": {"pipeline_version": "v1", "run_id": "run-1", "status": "ok"},
        "source_bundle": {
            "author_handle": "abc",
            "post_ids": ["p1"],
            "post_urls": ["https://x.com/x/status/p1"],
            "timestamps_utc": ["2026-01-01T00:00:00Z"],
        },
        "knowledge_extract": {
            "terms_detected": [
                {"term": "IFVG", "normalized_term": "ifvg", "category": "concept", "status": "observed", "evidence_refs": ["ocr:i1"], "confidence": None}
            ],
            "definitions_candidate": [],
            "relations_candidate": [],
            "variants_candidate": [],
            "contradictions_or_ambiguities": [],
        },
        "contextor_mapping_candidates": {"potential_events": [], "potential_questions": [], "potential_play_candidates": []},
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
        "quality_control": {"missing_data": [], "uncertainties": [], "possible_hallucination_risks": [], "needs_human_review": True},
        "provenance_index": [{"ref_id": "ocr:i1"}],
    }


def _record_report() -> dict:
    return {
        "record_index": 0,
        "post_id": "p1",
        "job_status": "ok",
        "canonicalization": {"actions": [{"action": "alias_map", "path": "x", "detail": "a->b"}], "pre_stats": {"empty_image_descriptions_skeleton_count": 0}},
        "validation": {
            "errors": [],
            "warnings": [],
            "metrics": {
                "evidence_resolution_rate": 1.0,
                "provenance_utilization_rate": 0.5,
                "semantic_items_total": 1,
                "observed_hedging_warnings_count": 0,
            },
        },
    }


def test_export_library_ready_and_reject_shapes() -> None:
    gate_report = {
        "run_gate_passed": True,
        "record_decision_summary": [
            {
                "record_index": 0,
                "post_id": "p1",
                "job_status": "ok",
                "passed": False,
                "blocking_error_count": 0,
                "blocking_warning_count": 1,
                "error_category_counts": {},
                "warning_category_counts": {"semantic": 1},
                "errors": [],
                "warnings": [{"code": "inferred_without_evidence", "category": "semantic", "severity": "blocking_warning", "message": "No evidence"}],
            }
        ],
    }
    result = export_knowledge_library_streams([_canonical_record()], [_record_report()], gate_report)
    assert result["export_report"]["ready_count"] == 0
    assert result["export_report"]["reject_count"] == 1
    reject = result["reject_records"][0]
    assert reject["gate_result"]["record_gate_passed"] is False
    assert reject["gate_result"]["reject_reasons"][0]["code"] == "inferred_without_evidence"


def test_export_library_ready_includes_canonical_record_and_snapshot() -> None:
    gate_report = {
        "run_gate_passed": True,
        "record_decision_summary": [
            {
                "record_index": 0,
                "post_id": "p1",
                "job_status": "ok",
                "passed": True,
                "blocking_error_count": 0,
                "blocking_warning_count": 0,
                "error_category_counts": {},
                "warning_category_counts": {"semantic": 0},
                "errors": [],
                "warnings": [],
            }
        ],
    }
    result = export_knowledge_library_streams([_canonical_record()], [_record_report()], gate_report)
    ready = result["ready_records"][0]
    assert ready["library_ingest_meta"]["export_gate_passed"] is True
    assert ready["source_ref"]["post_id"] == "p1"
    assert "canonical_record" in ready
    assert "quality_snapshot" in ready

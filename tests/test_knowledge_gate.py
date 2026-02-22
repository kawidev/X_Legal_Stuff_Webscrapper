from x_legal_stuff_webscrapper.knowledge_gate import (
    default_export_gate_policy,
    evaluate_record_export_gate,
    evaluate_run_export_gate,
    load_export_gate_policy_from_json,
    merge_export_gate_policy,
)


def _record_report(*, warnings=None, errors=None, schema_errors=None, idx=0) -> dict:
    return {
        "record_index": idx,
        "post_id": f"p{idx}",
        "job_status": "ok",
        "validation": {
            "errors": errors or [],
            "warnings": warnings or [],
            "metrics": {},
            "schema_contract": {"ok": not bool(schema_errors), "errors": schema_errors or []},
        },
    }


def test_record_gate_blocks_on_blocking_warning() -> None:
    report = _record_report(
        warnings=[{"code": "inferred_without_evidence", "path": "x", "message": "No evidence"}]
    )
    decision = evaluate_record_export_gate(report)
    assert decision["passed"] is False
    assert decision["blocking_warning_count"] == 1


def test_record_gate_allows_non_blocking_warning() -> None:
    report = _record_report(
        warnings=[{"code": "observed_hedging_language", "path": "x", "message": "hedge"}]
    )
    decision = evaluate_record_export_gate(report)
    assert decision["passed"] is True
    assert decision["warning_category_counts"]["semantic"] == 1


def test_record_gate_blocks_on_schema_contract_errors() -> None:
    report = _record_report(schema_errors=[{"loc": ["knowledge_extract", "terms_detected"], "msg": "bad", "type": "x"}])
    decision = evaluate_record_export_gate(report)
    assert decision["passed"] is False
    assert decision["blocking_error_count"] == 1


def test_record_gate_can_block_partial_by_policy() -> None:
    report = _record_report(idx=0)
    report["job_status"] = "partial"
    policy = default_export_gate_policy()
    policy["job_status_rules"]["allow_partial"] = False
    policy["blocking_warning_codes"] = list(policy["blocking_warning_codes"]) + ["partial_record_disallowed"]
    decision = evaluate_record_export_gate(report, policy=policy)
    assert decision["passed"] is False
    assert any(w["code"] == "partial_record_disallowed" for w in decision["warnings"])


def test_record_gate_threshold_generates_blocking_semantic_warning() -> None:
    report = _record_report(warnings=[{"code": "observed_hedging_language", "path": "x", "message": "hedge"}], idx=0)
    policy = default_export_gate_policy()
    policy["record_thresholds"]["max_warning_categories"] = {"semantic": 0}
    policy["blocking_warning_codes"] = list(policy["blocking_warning_codes"]) + ["semantic_warnings_above_threshold"]
    decision = evaluate_record_export_gate(report, policy=policy)
    assert decision["passed"] is False
    assert any(w["code"] == "semantic_warnings_above_threshold" for w in decision["warnings"])


def test_run_gate_applies_thresholds() -> None:
    policy = default_export_gate_policy()
    qa_report = {
        "quality_gate_metrics": {
            "broken_refs_count": 0,
            "evidence_resolution_rate": 0.5,
            "semantic_items_with_evidence_rate": 1.0,
        }
    }
    result = evaluate_run_export_gate(
        canonical_records=[{"id": 1}],
        record_reports=[_record_report(idx=0)],
        qa_report=qa_report,
        policy=policy,
    )
    assert result["gate_report"]["run_gate_passed"] is False
    assert result["gate_report"]["run_threshold_issues"]


def test_merge_export_gate_policy_overrides_nested_thresholds() -> None:
    merged = merge_export_gate_policy(default_export_gate_policy(), {"run_thresholds": {"max_broken_refs_count": 2}})
    assert merged["run_thresholds"]["max_broken_refs_count"] == 2


def test_load_export_gate_policy_from_json_supports_utf8_bom(tmp_path) -> None:
    path = tmp_path / "policy.json"
    path.write_text('{"run_thresholds":{"max_broken_refs_count":3}}', encoding="utf-8-sig")
    policy = load_export_gate_policy_from_json(path)
    assert policy["run_thresholds"]["max_broken_refs_count"] == 3

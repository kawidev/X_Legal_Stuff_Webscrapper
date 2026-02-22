from __future__ import annotations

from collections import Counter
from typing import Any


STRUCTURAL_CODES = {
    "missing_top_level_section",
    "invalid_type",
    "invalid_item_type",
    "invalid_semantic_status",
    "invalid_candidate_status",
    "invalid_evidence_refs_type",
    "invalid_evidence_ref_item_type",
    "missing_status_after_canonicalization",
    "schema_contract_error",
}
PROVENANCE_CODES = {
    "broken_evidence_ref",
    "provenance_resolution_below_threshold",
    "provenance_utilization_below_threshold",
}
SEMANTIC_CODES = {
    "observed_hedging_language",
    "uncertain_high_confidence",
    "inferred_without_evidence",
}
COMPLETENESS_CODES = {
    "partial_without_missing_data_reason",
}


def categorize_issue(code: str) -> str:
    if code in STRUCTURAL_CODES:
        return "structural"
    if code in PROVENANCE_CODES:
        return "provenance"
    if code in SEMANTIC_CODES:
        return "semantic"
    if code in COMPLETENESS_CODES:
        return "completeness"
    return "other"


def default_export_gate_policy() -> dict[str, Any]:
    return {
        "version": "knowledge-export-gate-v1",
        "blocking_error_categories": ["structural", "provenance", "semantic", "completeness", "other"],
        "blocking_warning_codes": [
            "missing_status_after_canonicalization",
            "inferred_without_evidence",
        ],
        "run_thresholds": {
            "min_evidence_resolution_rate": 1.0,
            "min_semantic_items_with_evidence_rate": 1.0,
            "max_broken_refs_count": 0,
        },
    }


def _schema_contract_issues(record_report: dict) -> list[dict]:
    schema = (((record_report.get("validation") or {}).get("schema_contract")) or {})
    issues = []
    for err in schema.get("errors") or []:
        issues.append(
            {
                "code": "schema_contract_error",
                "path": ".".join(err.get("loc") or []),
                "message": err.get("msg", ""),
                "details": err,
            }
        )
    return issues


def evaluate_record_export_gate(record_report: dict, policy: dict | None = None) -> dict[str, Any]:
    policy = policy or default_export_gate_policy()
    validation = record_report.get("validation") or {}
    errors = list(validation.get("errors") or [])
    warnings = list(validation.get("warnings") or [])
    errors.extend(_schema_contract_issues(record_report))

    normalized_errors = []
    normalized_warnings = []
    category_counts = {"errors": Counter(), "warnings": Counter()}
    blocking_warnings = []

    for issue in errors:
        code = str(issue.get("code") or "unknown_error")
        category = categorize_issue(code)
        category_counts["errors"][category] += 1
        normalized_errors.append({**issue, "category": category, "severity": "blocking_error"})

    for issue in warnings:
        code = str(issue.get("code") or "unknown_warning")
        category = categorize_issue(code)
        category_counts["warnings"][category] += 1
        severity = "blocking_warning" if code in set(policy.get("blocking_warning_codes") or []) else "warning"
        row = {**issue, "category": category, "severity": severity}
        normalized_warnings.append(row)
        if severity == "blocking_warning":
            blocking_warnings.append(row)

    passed = len(normalized_errors) == 0 and len(blocking_warnings) == 0
    return {
        "record_index": record_report.get("record_index"),
        "post_id": record_report.get("post_id"),
        "job_status": record_report.get("job_status"),
        "passed": passed,
        "blocking_error_count": len(normalized_errors),
        "blocking_warning_count": len(blocking_warnings),
        "error_category_counts": dict(category_counts["errors"]),
        "warning_category_counts": dict(category_counts["warnings"]),
        "errors": normalized_errors,
        "warnings": normalized_warnings,
    }


def evaluate_run_export_gate(
    canonical_records: list[dict],
    record_reports: list[dict],
    qa_report: dict | None = None,
    policy: dict | None = None,
) -> dict[str, Any]:
    policy = policy or default_export_gate_policy()
    decisions = [evaluate_record_export_gate(r, policy=policy) for r in record_reports]
    pass_indexes = {int(d["record_index"]) for d in decisions if d.get("passed") is True and d.get("record_index") is not None}
    fail_indexes = {int(d["record_index"]) for d in decisions if d.get("passed") is not True and d.get("record_index") is not None}
    decisions_by_idx = {int(d["record_index"]): d for d in decisions if isinstance(d.get("record_index"), int)}

    accepted_records = [canonical_records[i] for i in sorted(pass_indexes) if 0 <= i < len(canonical_records)]
    rejected_records = [
        {
            "record_index": i,
            "post_id": decisions_by_idx[i]["post_id"],
            "gate_decision": decisions_by_idx[i],
            "record": canonical_records[i],
        }
        for i in sorted(fail_indexes)
        if 0 <= i < len(canonical_records)
    ]

    thresholds = (policy.get("run_thresholds") or {})
    qgm = ((qa_report or {}).get("quality_gate_metrics")) or {}
    run_issues = []
    if "max_broken_refs_count" in thresholds and qgm.get("broken_refs_count", 0) > thresholds["max_broken_refs_count"]:
        run_issues.append(
            {
                "code": "broken_refs_above_threshold",
                "category": "provenance",
                "severity": "blocking_run_threshold",
                "metric": "broken_refs_count",
                "value": qgm.get("broken_refs_count"),
                "threshold": thresholds["max_broken_refs_count"],
            }
        )
    if "min_evidence_resolution_rate" in thresholds and qgm.get("evidence_resolution_rate", 0.0) < thresholds["min_evidence_resolution_rate"]:
        run_issues.append(
            {
                "code": "provenance_resolution_below_threshold",
                "category": "provenance",
                "severity": "blocking_run_threshold",
                "metric": "evidence_resolution_rate",
                "value": qgm.get("evidence_resolution_rate"),
                "threshold": thresholds["min_evidence_resolution_rate"],
            }
        )
    if "min_semantic_items_with_evidence_rate" in thresholds and qgm.get("semantic_items_with_evidence_rate", 0.0) < thresholds["min_semantic_items_with_evidence_rate"]:
        run_issues.append(
            {
                "code": "semantic_evidence_rate_below_threshold",
                "category": "semantic",
                "severity": "blocking_run_threshold",
                "metric": "semantic_items_with_evidence_rate",
                "value": qgm.get("semantic_items_with_evidence_rate"),
                "threshold": thresholds["min_semantic_items_with_evidence_rate"],
            }
        )

    error_cats = Counter()
    warning_cats = Counter()
    for d in decisions:
        for k, v in (d.get("error_category_counts") or {}).items():
            error_cats[k] += int(v)
        for k, v in (d.get("warning_category_counts") or {}).items():
            warning_cats[k] += int(v)

    gate_report = {
        "gate_version": "knowledge-export-gate-v1",
        "policy": policy,
        "run_gate_passed": len(run_issues) == 0,
        "record_gate_passed_count": sum(1 for d in decisions if d["passed"]),
        "record_gate_failed_count": sum(1 for d in decisions if not d["passed"]),
        "record_decision_summary": decisions,
        "run_threshold_issues": run_issues,
        "issue_category_counts": {
            "errors": dict(error_cats),
            "warnings": dict(warning_cats),
        },
    }
    return {
        "gate_report": gate_report,
        "accepted_records": accepted_records,
        "rejected_records": rejected_records,
    }

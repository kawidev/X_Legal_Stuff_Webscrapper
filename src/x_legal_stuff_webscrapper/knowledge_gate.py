from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
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
    "structural_warnings_above_threshold",
    "missing_status_count_above_threshold",
}
PROVENANCE_CODES = {
    "broken_evidence_ref",
    "provenance_resolution_below_threshold",
    "provenance_utilization_below_threshold",
    "provenance_warnings_above_threshold",
    "provenance_utilization_below_record_threshold",
}
SEMANTIC_CODES = {
    "observed_hedging_language",
    "uncertain_high_confidence",
    "inferred_without_evidence",
    "semantic_warnings_above_threshold",
    "observed_hedging_warnings_above_threshold",
}
COMPLETENESS_CODES = {
    "partial_without_missing_data_reason",
    "partial_record_disallowed",
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
        "record_thresholds": {
            "max_warning_categories": {},
            "max_missing_status_count": None,
            "max_observed_hedging_warnings_count": None,
            "min_provenance_utilization_rate": None,
        },
        "job_status_rules": {
            "allow_partial": True,
        },
    }


def merge_export_gate_policy(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_export_gate_policy(out[key], value)
        else:
            out[key] = value
    return out


def load_export_gate_policy_from_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Policy JSON must be an object")
    return merge_export_gate_policy(default_export_gate_policy(), data)


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
    metrics = validation.get("metrics") or {}
    job_status = str(record_report.get("job_status") or "unknown")

    warning_counts_pre = Counter(categorize_issue(str(w.get("code") or "")) for w in warnings)
    record_thresholds = (policy.get("record_thresholds") or {})
    max_warning_categories = record_thresholds.get("max_warning_categories") or {}
    for cat, limit in max_warning_categories.items():
        if limit is None:
            continue
        count = int(warning_counts_pre.get(cat, 0))
        if count > int(limit):
            code = f"{cat}_warnings_above_threshold"
            warnings.append(
                {
                    "code": code,
                    "path": "validation.warnings",
                    "message": f"{cat} warnings count {count} exceeds threshold {limit}",
                }
            )

    max_missing_status = record_thresholds.get("max_missing_status_count")
    if max_missing_status is not None and int(metrics.get("missing_status_count", 0) or 0) > int(max_missing_status):
        warnings.append(
            {
                "code": "missing_status_count_above_threshold",
                "path": "validation.metrics.missing_status_count",
                "message": f"missing_status_count {metrics.get('missing_status_count', 0)} exceeds threshold {max_missing_status}",
            }
        )
    max_hedge = record_thresholds.get("max_observed_hedging_warnings_count")
    if max_hedge is not None and int(metrics.get("observed_hedging_warnings_count", 0) or 0) > int(max_hedge):
        warnings.append(
            {
                "code": "observed_hedging_warnings_above_threshold",
                "path": "validation.metrics.observed_hedging_warnings_count",
                "message": f"observed_hedging_warnings_count {metrics.get('observed_hedging_warnings_count', 0)} exceeds threshold {max_hedge}",
            }
        )
    min_record_prov_util = record_thresholds.get("min_provenance_utilization_rate")
    if min_record_prov_util is not None and float(metrics.get("provenance_utilization_rate", 0.0) or 0.0) < float(min_record_prov_util):
        warnings.append(
            {
                "code": "provenance_utilization_below_record_threshold",
                "path": "validation.metrics.provenance_utilization_rate",
                "message": f"provenance_utilization_rate {metrics.get('provenance_utilization_rate', 0.0)} below threshold {min_record_prov_util}",
            }
        )

    job_status_rules = (policy.get("job_status_rules") or {})
    if job_status == "partial" and job_status_rules.get("allow_partial") is False:
        warnings.append(
            {
                "code": "partial_record_disallowed",
                "path": "job_meta.status",
                "message": "job_status=partial is disallowed by policy",
            }
        )

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
    if "min_provenance_utilization_rate" in thresholds and thresholds.get("min_provenance_utilization_rate") is not None and qgm.get("provenance_utilization_rate", 0.0) < thresholds["min_provenance_utilization_rate"]:
        run_issues.append(
            {
                "code": "provenance_utilization_below_threshold",
                "category": "provenance",
                "severity": "blocking_run_threshold",
                "metric": "provenance_utilization_rate",
                "value": qgm.get("provenance_utilization_rate"),
                "threshold": thresholds["min_provenance_utilization_rate"],
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

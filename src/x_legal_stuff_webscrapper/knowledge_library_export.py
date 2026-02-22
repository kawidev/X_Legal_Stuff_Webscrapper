from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _warning_counts_from_gate_decision(decision: dict) -> dict[str, int]:
    counts = {"structural": 0, "semantic": 0, "provenance": 0, "other": 0}
    for key, value in (decision.get("warning_category_counts") or {}).items():
        if key in counts:
            counts[key] = int(value)
        else:
            counts["other"] += int(value)
    return counts


def _error_count_from_gate_decision(decision: dict) -> int:
    return int(decision.get("blocking_error_count") or 0)


def _source_ref_from_canonical(record: dict) -> dict[str, Any]:
    source = record.get("source_bundle") or {}
    post_ids = source.get("post_ids") if isinstance(source.get("post_ids"), list) else []
    post_urls = source.get("post_urls") if isinstance(source.get("post_urls"), list) else []
    timestamps = source.get("timestamps_utc") if isinstance(source.get("timestamps_utc"), list) else []
    return {
        "post_id": str(post_ids[0]) if post_ids else "unknown",
        "post_url": post_urls[0] if post_urls else None,
        "author_handle": source.get("author_handle"),
        "timestamp_utc": timestamps[0] if timestamps else None,
    }


def _quality_snapshot(record: dict, record_report: dict, gate_decision: dict) -> dict[str, Any]:
    metrics = ((record_report.get("validation") or {}).get("metrics")) or {}
    return {
        "job_status": str(((record.get("job_meta") or {}).get("status")) or "unknown"),
        "warning_counts": _warning_counts_from_gate_decision(gate_decision),
        "evidence_resolution_rate": float(metrics.get("evidence_resolution_rate", 0.0) or 0.0),
        "provenance_utilization_rate": float(metrics.get("provenance_utilization_rate", 0.0) or 0.0),
        "error_count": _error_count_from_gate_decision(gate_decision),
    }


def _curation_hints(record: dict, record_report: dict, gate_decision: dict) -> dict[str, Any]:
    kx = (record.get("knowledge_extract") or {})
    metrics = ((record_report.get("validation") or {}).get("metrics")) or {}
    suggested_focus = []
    if (kx.get("terms_detected") or []) or (kx.get("definitions_candidate") or []):
        suggested_focus.append("terms")
        suggested_focus.append("definitions")
    if (kx.get("relations_candidate") or []):
        suggested_focus.append("relations")
    cmc = (record.get("contextor_mapping_candidates") or {})
    if any(cmc.get(key) for key in ["potential_events", "potential_questions", "potential_play_candidates"]):
        suggested_focus.append("contextor_mapping")
    # preserve order, remove duplicates
    seen = set()
    suggested_focus = [x for x in suggested_focus if not (x in seen or seen.add(x))]

    notes = []
    if str(((record.get("job_meta") or {}).get("status")) or "") == "partial":
        notes.append("job_status_partial")
    if int(metrics.get("observed_hedging_warnings_count", 0) or 0) > 0:
        notes.append("observed_hedging_present")
    if int(record_report.get("canonicalization", {}).get("pre_stats", {}).get("empty_image_descriptions_skeleton_count", 0) or 0) > 0:
        notes.append("image_description_skeleton_detected")
    if len(record_report.get("canonicalization", {}).get("actions", []) or []) > 0:
        notes.append("canonicalization_applied")

    semantic_count = int(metrics.get("semantic_items_total", 0) or 0)
    warning_counts = _warning_counts_from_gate_decision(gate_decision)
    if gate_decision.get("passed") and semantic_count >= 10 and warning_counts.get("semantic", 0) == 0:
        priority = "high"
    elif gate_decision.get("passed") and semantic_count >= 4:
        priority = "medium"
    else:
        priority = "low"

    return {
        "priority": priority,
        "suggested_focus": suggested_focus or ["terms"],
        "notes": notes,
    }


def build_library_ready_record(
    record: dict,
    record_report: dict,
    gate_decision: dict,
    *,
    schema_contract_version: str,
) -> dict[str, Any]:
    job_meta = record.get("job_meta") or {}
    return {
        "library_ingest_meta": {
            "ingested_at_utc": _utc_now_iso(),
            "pipeline_version": job_meta.get("pipeline_version"),
            "run_id": job_meta.get("run_id"),
            "schema_contract_version": schema_contract_version,
            "qa_passed": len(((record_report.get("validation") or {}).get("errors")) or []) == 0,
            "export_gate_passed": bool(gate_decision.get("passed")),
        },
        "source_ref": _source_ref_from_canonical(record),
        "quality_snapshot": {
            "job_status": str(((record.get("job_meta") or {}).get("status")) or "unknown"),
            "warning_counts": _warning_counts_from_gate_decision(gate_decision),
            "evidence_resolution_rate": float((((record_report.get("validation") or {}).get("metrics")) or {}).get("evidence_resolution_rate", 0.0) or 0.0),
            "provenance_utilization_rate": float((((record_report.get("validation") or {}).get("metrics")) or {}).get("provenance_utilization_rate", 0.0) or 0.0),
        },
        "canonical_record": record,
        "curation_hints": _curation_hints(record, record_report, gate_decision),
    }


def build_library_reject_record(
    record: dict,
    record_report: dict,
    gate_decision: dict,
) -> dict[str, Any]:
    job_meta = record.get("job_meta") or {}
    metrics = ((record_report.get("validation") or {}).get("metrics")) or {}
    reasons = []
    for issue in (gate_decision.get("errors") or []):
        reasons.append(
            {
                "code": issue.get("code"),
                "severity": "error",
                "category": issue.get("category", "other"),
                "message": issue.get("message", ""),
            }
        )
    for issue in (gate_decision.get("warnings") or []):
        if issue.get("severity") in {"blocking_warning", "blocking_error"}:
            reasons.append(
                {
                    "code": issue.get("code"),
                    "severity": "warning",
                    "category": issue.get("category", "other"),
                    "message": issue.get("message", ""),
                }
            )
    if not reasons and not bool(gate_decision.get("passed")):
        reasons.append(
            {
                "code": "gate_failed_without_explicit_reason",
                "severity": "error",
                "category": "other",
                "message": "Record failed export gate but no blocking issue was captured in decision payload.",
            }
        )
    return {
        "reject_meta": {
            "rejected_at_utc": _utc_now_iso(),
            "pipeline_version": job_meta.get("pipeline_version"),
            "run_id": job_meta.get("run_id"),
        },
        "source_ref": {
            "post_id": _source_ref_from_canonical(record)["post_id"],
            "post_url": _source_ref_from_canonical(record)["post_url"],
        },
        "gate_result": {
            "record_gate_passed": bool(gate_decision.get("passed")),
            "reject_reasons": reasons,
        },
        "quality_snapshot": {
            "job_status": str(((record.get("job_meta") or {}).get("status")) or "unknown"),
            "warning_counts": _warning_counts_from_gate_decision(gate_decision),
            "error_count": _error_count_from_gate_decision(gate_decision),
            "evidence_resolution_rate": float(metrics.get("evidence_resolution_rate", 0.0) or 0.0),
            "provenance_utilization_rate": float(metrics.get("provenance_utilization_rate", 0.0) or 0.0),
        },
    }


def export_knowledge_library_streams(
    canonical_records: list[dict],
    record_reports: list[dict],
    gate_report: dict,
    *,
    schema_contract_version: str = "knowledge-canonical-contract-v1",
) -> dict[str, Any]:
    decisions = (gate_report.get("record_decision_summary") or [])
    decisions_by_index = {
        int(d["record_index"]): d
        for d in decisions
        if isinstance(d, dict) and isinstance(d.get("record_index"), int)
    }

    ready = []
    rejects = []
    for idx, record in enumerate(canonical_records):
        record_report = record_reports[idx] if idx < len(record_reports) else {}
        gate_decision = decisions_by_index.get(
            idx,
            {
                "record_index": idx,
                "post_id": str((((record.get("source_bundle") or {}).get("post_ids")) or ["unknown"])[0]),
                "job_status": str(((record.get("job_meta") or {}).get("status")) or "unknown"),
                "passed": False,
                "errors": [
                    {
                        "code": "missing_gate_decision",
                        "message": "No gate decision found for record index",
                        "category": "other",
                        "severity": "blocking_error",
                    }
                ],
                "warnings": [],
                "warning_category_counts": {},
                "error_category_counts": {"other": 1},
                "blocking_error_count": 1,
                "blocking_warning_count": 0,
            },
        )
        if gate_decision.get("passed") is True:
            ready.append(
                build_library_ready_record(
                    record,
                    record_report,
                    gate_decision,
                    schema_contract_version=schema_contract_version,
                )
            )
        else:
            rejects.append(build_library_reject_record(record, record_report, gate_decision))

    export_report = {
        "export_version": "knowledge-library-export-v1",
        "schema_contract_version": schema_contract_version,
        "input_record_count": len(canonical_records),
        "ready_count": len(ready),
        "reject_count": len(rejects),
        "run_gate_passed": bool(gate_report.get("run_gate_passed")),
    }
    return {"ready_records": ready, "reject_records": rejects, "export_report": export_report}

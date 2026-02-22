from __future__ import annotations

import copy
import re
from collections import Counter
from typing import Any

from .knowledge_gate import categorize_issue
from .knowledge_schema import validate_canonical_knowledge_contract


SEMANTIC_STATUS_ALLOWED = {"observed", "inferred", "uncertain"}
MAPPING_STATUS_ALLOWED = {"candidate"}
TRADING_CONTEXT_KEYS = [
    "htf_elements",
    "ltf_elements",
    "time_windows_mentioned",
    "poi_elements",
    "liquidity_elements",
    "execution_elements",
    "invalidation_elements",
    "outcome_elements",
]
HEDGING_RE = re.compile(r"\b(likely|presumably|may|could|appears|implies|suggests)\b", re.IGNORECASE)


def _ensure_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _ensure_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _normalize_term(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text.replace("&amp;", "&")


def _infer_term_status_fallback(item: dict) -> str:
    evidence_refs = item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else []
    has_direct_evidence_ref = any(
        isinstance(ref, str) and (ref.startswith("post:") or ref.startswith("ocr:")) for ref in evidence_refs
    )
    has_interpretive_payload = any(
        isinstance(item.get(key), str) and item.get(key).strip()
        for key in ["definition", "definition_text", "description", "heuristic", "warning"]
    )
    if has_direct_evidence_ref and not has_interpretive_payload:
        return "observed"
    return "uncertain"


def _slugify(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return out[:80] or "unknown"


def _action(actions: list[dict], action: str, path: str, detail: str | None = None) -> None:
    row = {"action": action, "path": path}
    if detail:
        row["detail"] = detail
    actions.append(row)


def _pre_stats(record: dict) -> dict:
    mixed = 0

    def walk(obj: Any) -> None:
        nonlocal mixed
        if isinstance(obj, list):
            types = {type(x).__name__ for x in obj if x is not None}
            if len(types) > 1:
                mixed += 1
            for x in obj:
                walk(x)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)

    walk(record)
    image_desc = (((record.get("raw_capture") or {}).get("image_descriptions")) or [])
    empty_img_desc = 0
    for item in image_desc:
        if isinstance(item, dict) and item.get("observed_visual_elements") in ([], None) and item.get("chart_timeframe") is None and item.get("instrument_hint") is None and item.get("confidence") in (0, 0.0, None):
            empty_img_desc += 1
    return {"mixed_type_arrays_count": mixed, "empty_image_descriptions_skeleton_count": empty_img_desc}


def _ensure_top_level(c: dict, actions: list[dict]) -> None:
    required = {
        "job_meta": {},
        "source_bundle": {},
        "raw_capture": {},
        "knowledge_extract": {},
        "trading_context_extract": {},
        "contextor_mapping_candidates": {},
        "quality_control": {"missing_data": [], "uncertainties": [], "possible_hallucination_risks": [], "needs_human_review": True},
        "provenance_index": [],
    }
    for key, default in required.items():
        if key not in c or not isinstance(c.get(key), type(default)):
            c[key] = copy.deepcopy(default)
            _action(actions, "ensure_top_level", key)

    kx = _ensure_dict(c["knowledge_extract"])
    for key in ["terms_detected", "definitions_candidate", "relations_candidate", "variants_candidate", "contradictions_or_ambiguities"]:
        if not isinstance(kx.get(key), list):
            kx[key] = []
            _action(actions, "ensure_list", f"knowledge_extract.{key}")
    c["knowledge_extract"] = kx

    cmc = _ensure_dict(c["contextor_mapping_candidates"])
    for key in ["potential_events", "potential_questions", "potential_play_candidates"]:
        if not isinstance(cmc.get(key), list):
            cmc[key] = []
            _action(actions, "ensure_list", f"contextor_mapping_candidates.{key}")
    c["contextor_mapping_candidates"] = cmc

    qc = _ensure_dict(c["quality_control"])
    for key in ["missing_data", "uncertainties", "possible_hallucination_risks"]:
        if not isinstance(qc.get(key), list):
            qc[key] = []
            _action(actions, "ensure_list", f"quality_control.{key}")
    if "needs_human_review" not in qc:
        qc["needs_human_review"] = True
        _action(actions, "fallback_fill", "quality_control.needs_human_review", "True")
    c["quality_control"] = qc


def _canon_terms_and_defs(c: dict, actions: list[dict]) -> None:
    kx = c["knowledge_extract"]
    defs = [copy.deepcopy(x) for x in _ensure_list(kx.get("definitions_candidate"))]
    out_terms = []
    for i, raw in enumerate(_ensure_list(kx.get("terms_detected"))):
        p = f"knowledge_extract.terms_detected[{i}]"
        item = {"term": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"term": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        if "interpretation_status" in item and "status" not in item:
            item["status"] = item["interpretation_status"]
            _action(actions, "alias_map", p, "interpretation_status->status")
        if "concept" in item and "term" not in item:
            item["term"] = item["concept"]
            _action(actions, "alias_map", p, "concept->term")
        if not item.get("term"):
            item["term"] = "unknown"
            _action(actions, "fallback_fill", p, "term=unknown")
        if not item.get("normalized_term"):
            item["normalized_term"] = _normalize_term(str(item["term"]))
            _action(actions, "fallback_fill", p, "normalized_term")
        if not item.get("category"):
            item["category"] = "concept"
            _action(actions, "fallback_fill", p, "category=concept")
        if "confidence" not in item:
            item["confidence"] = None
            _action(actions, "fallback_fill", p, "confidence=null")
        if not item.get("status"):
            inferred_status = _infer_term_status_fallback(item)
            item["status"] = inferred_status
            _action(actions, "fallback_fill", p, f"status={inferred_status}")
        if "evidence_refs" not in item:
            item["evidence_refs"] = []
            _action(actions, "fallback_fill", p, "evidence_refs=[]")
        elif not isinstance(item["evidence_refs"], list):
            item["evidence_refs"] = _ensure_list(item["evidence_refs"])
            _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        if item.get("definition"):
            defs.append(
                {
                    "term": item["term"],
                    "definition_text": item["definition"],
                    "definition_type": "operational_candidate",
                    "status": item["status"],
                    "evidence_refs": item.get("evidence_refs", []),
                    "confidence": item.get("confidence"),
                }
            )
            _action(actions, "move_term_definition", f"{p}.definition")
        out_terms.append(item)
    kx["terms_detected"] = out_terms
    kx["definitions_candidate"] = defs


def _canon_defs_rels_variants(c: dict, actions: list[dict]) -> None:
    kx = c["knowledge_extract"]
    defs_out = []
    for i, raw in enumerate(_ensure_list(kx.get("definitions_candidate"))):
        p = f"knowledge_extract.definitions_candidate[{i}]"
        item = {"definition_text": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"definition_text": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        if "concept" in item and "term" not in item:
            item["term"] = item["concept"]
            _action(actions, "alias_map", p, "concept->term")
        if "definition" in item and "definition_text" not in item:
            item["definition_text"] = item["definition"]
            _action(actions, "alias_map", p, "definition->definition_text")
        item.setdefault("term", "unknown")
        item.setdefault("definition_text", "")
        item.setdefault("definition_type", "operational_candidate")
        item.setdefault("status", "inferred")
        item.setdefault("confidence", None)
        item.setdefault("evidence_refs", [])
        if not isinstance(item["evidence_refs"], list):
            item["evidence_refs"] = _ensure_list(item["evidence_refs"])
            _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        defs_out.append(item)
    kx["definitions_candidate"] = defs_out

    rels_out = []
    for i, raw in enumerate(_ensure_list(kx.get("relations_candidate"))):
        p = f"knowledge_extract.relations_candidate[{i}]"
        item = {"relation": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"relation": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        for a, b in [("from", "subject"), ("source", "subject"), ("to", "object"), ("target", "object"), ("property", "relation")]:
            if a in item and b not in item:
                item[b] = item[a]
                _action(actions, "alias_map", p, f"{a}->{b}")
        item.setdefault("subject", "unknown")
        item.setdefault("object", "unknown")
        item.setdefault("relation", "related_to")
        item.setdefault("status", "inferred")
        item.setdefault("confidence", None)
        item.setdefault("evidence_refs", [])
        if not isinstance(item["evidence_refs"], list):
            item["evidence_refs"] = _ensure_list(item["evidence_refs"])
            _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        rels_out.append(item)
    kx["relations_candidate"] = rels_out

    var_out = []
    for i, raw in enumerate(_ensure_list(kx.get("variants_candidate"))):
        p = f"knowledge_extract.variants_candidate[{i}]"
        item = {"variant_name": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"variant_name": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        if "name" in item and "variant_name" not in item:
            item["variant_name"] = item["name"]
            _action(actions, "alias_map", p, "name->variant_name")
        item.setdefault("parent_term", "unknown")
        item.setdefault("variant_name", "unknown_variant")
        item.setdefault("description", "")
        item.setdefault("status", "inferred")
        item.setdefault("confidence", None)
        item.setdefault("evidence_refs", [])
        var_out.append(item)
    kx["variants_candidate"] = var_out


def _canon_context_and_mapping(c: dict, actions: list[dict]) -> None:
    cmc = c["contextor_mapping_candidates"]
    events = []
    for i, raw in enumerate(_ensure_list(cmc.get("potential_events"))):
        p = f"contextor_mapping_candidates.potential_events[{i}]"
        item = {"name": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"name": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        if "event" in item and "name" not in item:
            item["name"] = item["event"]
            _action(actions, "alias_map", p, "event->name")
        item.setdefault("name", "unknown_event")
        item.setdefault("description", item.get("name", ""))
        item.setdefault("source_terms", [])
        item.setdefault("status", "candidate")
        item.setdefault("evidence_refs", [])
        if not isinstance(item["source_terms"], list):
            item["source_terms"] = _ensure_list(item["source_terms"])
            _action(actions, "coerce_to_list", f"{p}.source_terms")
        if not isinstance(item["evidence_refs"], list):
            item["evidence_refs"] = _ensure_list(item["evidence_refs"])
            _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        events.append(item)
    cmc["potential_events"] = events

    questions = []
    for i, raw in enumerate(_ensure_list(cmc.get("potential_questions"))):
        p = f"contextor_mapping_candidates.potential_questions[{i}]"
        if isinstance(raw, str):
            item = {
                "question_key_candidate": _slugify(raw),
                "question_text": raw,
                "scope": "unknown",
                "trigger_terms": [],
                "status": "candidate",
                "evidence_refs": [],
            }
            _action(actions, "coerce_string_to_question_dict", p)
        else:
            item = copy.deepcopy(raw) if isinstance(raw, dict) else {"question_text": str(raw)}
            if not isinstance(raw, dict):
                _action(actions, "coerce_to_dict", p)
            if "question" in item and "question_text" not in item:
                item["question_text"] = item["question"]
                _action(actions, "alias_map", p, "question->question_text")
            item.setdefault("question_text", "")
            item.setdefault("question_key_candidate", _slugify(item.get("question_text", "")))
            item.setdefault("scope", "unknown")
            item.setdefault("trigger_terms", [])
            item.setdefault("status", "candidate")
            item.setdefault("evidence_refs", [])
            if not isinstance(item["trigger_terms"], list):
                item["trigger_terms"] = _ensure_list(item["trigger_terms"])
                _action(actions, "coerce_to_list", f"{p}.trigger_terms")
            if not isinstance(item["evidence_refs"], list):
                item["evidence_refs"] = _ensure_list(item["evidence_refs"])
                _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        questions.append(item)
    cmc["potential_questions"] = questions

    plays = []
    for i, raw in enumerate(_ensure_list(cmc.get("potential_play_candidates"))):
        p = f"contextor_mapping_candidates.potential_play_candidates[{i}]"
        item = {"name": raw} if isinstance(raw, str) else copy.deepcopy(raw) if isinstance(raw, dict) else {"name": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        for alias in ["play", "play_name"]:
            if alias in item and "name" not in item:
                item["name"] = item[alias]
                _action(actions, "alias_map", p, f"{alias}->name")
        item.setdefault("name", "unknown_play")
        item.setdefault("family", "scenario")
        item.setdefault("description", item.get("name", ""))
        item.setdefault("status", "candidate")
        item.setdefault("evidence_refs", [])
        if not isinstance(item["evidence_refs"], list):
            item["evidence_refs"] = _ensure_list(item["evidence_refs"])
            _action(actions, "coerce_to_list", f"{p}.evidence_refs")
        plays.append(item)
    cmc["potential_play_candidates"] = plays
    c["contextor_mapping_candidates"] = cmc

    tce = _ensure_dict(c["trading_context_extract"])
    for key in TRADING_CONTEXT_KEYS:
        out = []
        for i, raw in enumerate(_ensure_list(tce.get(key))):
            p = f"trading_context_extract.{key}[{i}]"
            if isinstance(raw, str):
                out.append({"label": raw})
                _action(actions, "coerce_string_to_labeled_object", p)
                continue
            if isinstance(raw, dict):
                item = copy.deepcopy(raw)
                if "label" not in item:
                    for alias in ["element", "window", "poi", "liquidity_type", "outcome", "name", "description"]:
                        if isinstance(item.get(alias), str) and item.get(alias):
                            item["label"] = item[alias]
                            _action(actions, "fallback_fill", p, f"label<={alias}")
                            break
                out.append(item)
                continue
            out.append({"label": str(raw)})
            _action(actions, "coerce_scalar_to_labeled_object", p)
        tce[key] = out
    c["trading_context_extract"] = tce


def canonicalize_knowledge_record(record: dict) -> dict:
    canonical = copy.deepcopy(record)
    actions: list[dict] = []
    pre = _pre_stats(record)
    _ensure_top_level(canonical, actions)
    _canon_terms_and_defs(canonical, actions)
    _canon_defs_rels_variants(canonical, actions)
    _canon_context_and_mapping(canonical, actions)
    # provenance
    prov = []
    for i, raw in enumerate(_ensure_list(canonical.get("provenance_index"))):
        p = f"provenance_index[{i}]"
        item = copy.deepcopy(raw) if isinstance(raw, dict) else {"ref_id": str(raw)}
        if not isinstance(raw, dict):
            _action(actions, "coerce_to_dict", p)
        if not isinstance(item.get("ref_id"), str) or not item.get("ref_id"):
            item["ref_id"] = f"unknown_ref_{i}"
            _action(actions, "fallback_fill", p, "ref_id")
        prov.append(item)
    canonical["provenance_index"] = prov
    return {"canonical_record": canonical, "canonicalization_actions": actions, "pre_stats": pre}


def _iter_items(record: dict) -> list[dict]:
    out = []
    kx = _ensure_dict(record.get("knowledge_extract"))
    for sec in ["terms_detected", "definitions_candidate", "relations_candidate", "variants_candidate"]:
        for i, item in enumerate(_ensure_list(kx.get(sec))):
            if isinstance(item, dict):
                out.append({"kind": "semantic", "path": f"knowledge_extract.{sec}[{i}]", "item": item})
    cmc = _ensure_dict(record.get("contextor_mapping_candidates"))
    for sec in ["potential_events", "potential_questions", "potential_play_candidates"]:
        for i, item in enumerate(_ensure_list(cmc.get(sec))):
            if isinstance(item, dict):
                out.append({"kind": "candidate", "path": f"contextor_mapping_candidates.{sec}[{i}]", "item": item})
    return out


def _check_list_of_dict(path: str, value: Any, errors: list[dict]) -> None:
    if not isinstance(value, list):
        errors.append({"code": "invalid_type", "path": path, "message": "Expected list"})
        return
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append({"code": "invalid_item_type", "path": f"{path}[{i}]", "message": "Expected dict"})


def validate_canonical_knowledge_record(record: dict) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    for key in ["job_meta", "source_bundle", "raw_capture", "knowledge_extract", "trading_context_extract", "contextor_mapping_candidates", "quality_control", "provenance_index"]:
        if key not in record:
            errors.append({"code": "missing_top_level_section", "path": key, "message": "Missing"})

    kx = _ensure_dict(record.get("knowledge_extract"))
    for sec in ["terms_detected", "definitions_candidate", "relations_candidate", "variants_candidate"]:
        _check_list_of_dict(f"knowledge_extract.{sec}", kx.get(sec), errors)
    cmc = _ensure_dict(record.get("contextor_mapping_candidates"))
    for sec in ["potential_events", "potential_questions", "potential_play_candidates"]:
        _check_list_of_dict(f"contextor_mapping_candidates.{sec}", cmc.get(sec), errors)
    tce = _ensure_dict(record.get("trading_context_extract"))
    for key in TRADING_CONTEXT_KEYS:
        _check_list_of_dict(f"trading_context_extract.{key}", tce.get(key), errors)
    _check_list_of_dict("provenance_index", record.get("provenance_index"), errors)

    prov_ids = {x.get("ref_id") for x in _ensure_list(record.get("provenance_index")) if isinstance(x, dict) and isinstance(x.get("ref_id"), str)}
    used_refs = set()
    metrics = {
        "semantic_items_total": 0,
        "semantic_items_with_status": 0,
        "semantic_items_with_evidence": 0,
        "evidence_refs_total": 0,
        "evidence_refs_resolved": 0,
        "broken_refs_count": 0,
        "provenance_ref_count": len(prov_ids),
        "provenance_refs_used_count": 0,
        "missing_status_count": 0,
        "observed_hedging_warnings_count": 0,
        "uncertain_high_confidence_warnings_count": 0,
        "inferred_without_evidence_warnings_count": 0,
    }

    for meta in _iter_items(record):
        item = meta["item"]
        path = meta["path"]
        kind = meta["kind"]
        status = item.get("status")
        ev = item.get("evidence_refs", [])
        if kind == "semantic":
            metrics["semantic_items_total"] += 1
        if not status:
            metrics["missing_status_count"] += 1
            warnings.append({"code": "missing_status_after_canonicalization", "path": path, "message": "Missing status"})
        else:
            if kind == "semantic":
                metrics["semantic_items_with_status"] += 1
                if status not in SEMANTIC_STATUS_ALLOWED:
                    errors.append({"code": "invalid_semantic_status", "path": f"{path}.status", "message": str(status)})
            elif status not in MAPPING_STATUS_ALLOWED:
                warnings.append({"code": "invalid_candidate_status", "path": f"{path}.status", "message": str(status)})
        if not isinstance(ev, list):
            errors.append({"code": "invalid_evidence_refs_type", "path": f"{path}.evidence_refs", "message": "Expected list[str]"})
            ev = []
        elif kind == "semantic" and ev:
            metrics["semantic_items_with_evidence"] += 1
        for j, ref in enumerate(ev):
            metrics["evidence_refs_total"] += 1
            if not isinstance(ref, str):
                errors.append({"code": "invalid_evidence_ref_item_type", "path": f"{path}.evidence_refs[{j}]", "message": type(ref).__name__})
                continue
            if ref in prov_ids:
                metrics["evidence_refs_resolved"] += 1
                used_refs.add(ref)
            else:
                metrics["broken_refs_count"] += 1
                errors.append({"code": "broken_evidence_ref", "path": f"{path}.evidence_refs[{j}]", "message": ref})

        blob = " ".join(v for k, v in item.items() if isinstance(v, str) and k not in {"status", "category", "normalized_term"})
        if status == "observed" and HEDGING_RE.search(blob):
            metrics["observed_hedging_warnings_count"] += 1
            warnings.append({"code": "observed_hedging_language", "path": path, "message": "Hedging in observed item"})
        conf = item.get("confidence")
        if status == "uncertain" and isinstance(conf, (int, float)) and float(conf) >= 0.85:
            metrics["uncertain_high_confidence_warnings_count"] += 1
            warnings.append({"code": "uncertain_high_confidence", "path": f"{path}.confidence", "message": str(conf)})
        if status == "inferred" and not ev:
            metrics["inferred_without_evidence_warnings_count"] += 1
            warnings.append({"code": "inferred_without_evidence", "path": path, "message": "No evidence_refs"})

    metrics["provenance_refs_used_count"] = len(used_refs)
    metrics["evidence_resolution_rate"] = (metrics["evidence_refs_resolved"] / metrics["evidence_refs_total"]) if metrics["evidence_refs_total"] else 1.0
    metrics["provenance_utilization_rate"] = (metrics["provenance_refs_used_count"] / metrics["provenance_ref_count"]) if metrics["provenance_ref_count"] else 0.0
    metrics["semantic_items_with_evidence_rate"] = (metrics["semantic_items_with_evidence"] / metrics["semantic_items_total"]) if metrics["semantic_items_total"] else 0.0

    job_status = (_ensure_dict(record.get("job_meta")).get("status"))
    missing_data = (_ensure_dict(record.get("quality_control")).get("missing_data"))
    if job_status == "partial" and (not isinstance(missing_data, list) or len(missing_data) == 0):
        warnings.append({"code": "partial_without_missing_data_reason", "path": "quality_control.missing_data", "message": "partial without missing_data"})

    schema_contract = validate_canonical_knowledge_contract(record)
    metrics["schema_contract_error_count"] = len(schema_contract.get("errors") or [])
    return {"errors": errors, "warnings": warnings, "metrics": metrics, "schema_contract": schema_contract}


def run_quality_gates_for_knowledge_records(records: list[dict]) -> dict:
    canonical_records = []
    record_reports = []
    action_counts: Counter[str] = Counter()
    action_detail_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    error_category_counts: Counter[str] = Counter()
    warning_category_counts: Counter[str] = Counter()
    agg = {
        "error_count_total": 0,
        "warning_count_total": 0,
        "broken_refs_count": 0,
        "evidence_refs_total": 0,
        "evidence_refs_resolved": 0,
        "provenance_ref_count": 0,
        "provenance_refs_used_count": 0,
        "semantic_items_total": 0,
        "semantic_items_with_evidence": 0,
        "missing_status_count": 0,
        "observed_hedging_warnings_count": 0,
        "schema_contract_error_count_total": 0,
    }
    pre_schema = {"records_with_drift": 0, "mixed_type_arrays_count": 0, "mixed_type_arrays_records": 0, "empty_image_descriptions_skeleton_count": 0}

    for idx, rec in enumerate(records):
        canon = canonicalize_knowledge_record(rec)
        c = canon["canonical_record"]
        v = validate_canonical_knowledge_record(c)
        actions = canon["canonicalization_actions"]
        pre = canon["pre_stats"]
        post_id = ((_ensure_dict(c.get("source_bundle")).get("post_ids") or ["unknown"])[0]) if isinstance(_ensure_dict(c.get("source_bundle")).get("post_ids"), list) else "unknown"

        if actions:
            pre_schema["records_with_drift"] += 1
        if pre.get("mixed_type_arrays_count", 0):
            pre_schema["mixed_type_arrays_records"] += 1
        pre_schema["mixed_type_arrays_count"] += int(pre.get("mixed_type_arrays_count", 0))
        pre_schema["empty_image_descriptions_skeleton_count"] += int(pre.get("empty_image_descriptions_skeleton_count", 0))

        for a in actions:
            action_counts[a["action"]] += 1
            action_detail_counts[a.get("detail") or a["path"]] += 1
        for k in agg:
            if k in v["metrics"]:
                agg[k] += int(v["metrics"][k])
        agg["error_count_total"] += len(v["errors"])
        agg["warning_count_total"] += len(v["warnings"])
        agg["schema_contract_error_count_total"] += len((v.get("schema_contract") or {}).get("errors") or [])
        status_counts[str(_ensure_dict(c.get("job_meta")).get("status") or "unknown")] += 1
        for issue in v["errors"]:
            error_category_counts[categorize_issue(str(issue.get("code") or ""))] += 1
        for issue in (v.get("schema_contract") or {}).get("errors") or []:
            error_category_counts["structural"] += 1
        for issue in v["warnings"]:
            warning_category_counts[categorize_issue(str(issue.get("code") or ""))] += 1

        record_reports.append(
            {
                "record_index": idx,
                "post_id": str(post_id),
                "job_status": str(_ensure_dict(c.get("job_meta")).get("status") or "unknown"),
                "canonicalization": {"actions": actions, "pre_stats": pre},
                "validation": v,
            }
        )
        canonical_records.append(c)

    qa_report = {
        "qa_version": "knowledge-quality-gates-v1",
        "record_count": len(records),
        "status_counts": dict(status_counts),
        "schema_drift_stats_pre_canonicalization": pre_schema,
        "canonicalization_actions_count": dict(action_counts),
        "canonicalization_actions_by_detail_top20": dict(action_detail_counts.most_common(20)),
        "warning_category_counts": dict(warning_category_counts),
        "error_category_counts": dict(error_category_counts),
        "quality_gate_metrics": {
            **agg,
            "evidence_resolution_rate": (agg["evidence_refs_resolved"] / agg["evidence_refs_total"]) if agg["evidence_refs_total"] else 1.0,
            "provenance_utilization_rate": (agg["provenance_refs_used_count"] / agg["provenance_ref_count"]) if agg["provenance_ref_count"] else 0.0,
            "semantic_items_with_evidence_rate": (agg["semantic_items_with_evidence"] / agg["semantic_items_total"]) if agg["semantic_items_total"] else 0.0,
            "structural_warnings_count": int(warning_category_counts.get("structural", 0)),
            "semantic_warnings_count": int(warning_category_counts.get("semantic", 0)),
            "provenance_warnings_count": int(warning_category_counts.get("provenance", 0)),
        },
    }
    return {"canonical_records": canonical_records, "record_reports": record_reports, "qa_report": qa_report}

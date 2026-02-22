from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .classifier import classify_posts
from .collector_x import collect_public_posts
from .config import AppConfig
from .exporter import export_dataset
from .knowledge_gate import (
    default_export_gate_policy,
    evaluate_run_export_gate,
    load_export_gate_policy_from_json,
)
from .knowledge_extractor import extract_knowledge_records
from .knowledge_library_export import export_knowledge_library_streams
from .knowledge_quality import run_quality_gates_for_knowledge_records
from .knowledge_schema import canonical_knowledge_record_json_schema
from .llm_enrichment import enrich_posts
from .media_downloader import download_images_for_posts
from .storage import append_jsonl, ensure_dir, read_jsonl, write_json, write_jsonl
from .vision_ocr import DEFAULT_OCR_PROMPT, process_posts_for_ocr


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _paths(data_dir: Path) -> dict[str, Path]:
    return {
        "raw_posts": data_dir / "raw" / "posts.jsonl",
        "image_manifest": data_dir / "index" / "images_manifest.jsonl",
        "ocr": data_dir / "processed" / "ocr_results.jsonl",
        "knowledge": data_dir / "processed" / "knowledge_extract.jsonl",
        "knowledge_canonical": data_dir / "processed" / "knowledge_extract_canonical.jsonl",
        "knowledge_quality_records": data_dir / "processed" / "knowledge_quality_records.jsonl",
        "knowledge_qa_report": data_dir / "processed" / "knowledge_qa_report.json",
        "knowledge_schema": data_dir / "processed" / "knowledge_canonical.schema.json",
        "knowledge_export_gate_report": data_dir / "processed" / "knowledge_export_gate_report.json",
        "knowledge_export_pass": data_dir / "processed" / "knowledge_export_pass.jsonl",
        "knowledge_export_fail": data_dir / "processed" / "knowledge_export_fail.jsonl",
        "knowledge_library_ready": data_dir / "processed" / "knowledge_library_ready.jsonl",
        "knowledge_library_rejects": data_dir / "processed" / "knowledge_library_rejects.jsonl",
        "knowledge_library_export_report": data_dir / "processed" / "knowledge_library_export_report.json",
        "enrich": data_dir / "processed" / "llm_results.jsonl",
        "processed_posts": data_dir / "processed" / "posts.jsonl",
        "classifications": data_dir / "processed" / "classifications.jsonl",
        "export": data_dir / "exports" / "dataset.jsonl",
    }


def cmd_collect(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("collect")
    paths = _paths(config.data_dir)
    handles = args.accounts or config.x_source_accounts
    if not handles:
        logger.error("No source accounts provided. Use --account or X_SOURCE_ACCOUNTS.")
        return 2

    tag_filters = args.tags or config.x_filter_tags
    text_filters = args.queries or config.x_filter_keywords
    use_filters = args.mode == "filtered"
    backend = args.backend if args.backend != "auto" else config.x_collect_backend

    try:
        posts = collect_public_posts(
            handles=handles,
            limit_per_account=args.limit,
            backend=backend,
            x_api_bearer_token=config.x_api_bearer_token,
            tag_filters=tag_filters if use_filters else None,
            text_filters=text_filters if use_filters else None,
            match_mode=args.match_mode,
            content_mode=args.content_mode,
        )
    except Exception as exc:
        logger.error("Collect failed: %s", exc)
        return 1

    if args.download_images:
        posts, image_manifest = download_images_for_posts(posts, data_dir=config.data_dir)
        append_jsonl(paths["image_manifest"], image_manifest)
        logger.info("Downloaded/processed %s images", len(image_manifest))

    append_jsonl(paths["raw_posts"], posts)
    append_jsonl(paths["processed_posts"], posts)
    logger.info(
        "Collected %s posts from %s accounts (backend=%s, mode=%s, content_mode=%s, tags=%s, queries=%s, match=%s)",
        len(posts),
        len(handles),
        backend,
        "filtered" if use_filters else "all",
        args.content_mode,
        tag_filters if use_filters else [],
        text_filters if use_filters else [],
        args.match_mode,
    )
    return 0


def cmd_ocr(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("ocr")
    paths = _paths(config.data_dir)
    posts = read_jsonl(paths["processed_posts"])
    backend = args.backend
    if backend == "auto":
        backend = "openai-vision" if config.openai_api_key else "placeholder"
    try:
        results = process_posts_for_ocr(
            posts,
            data_dir=config.data_dir,
            backend=backend,
            openai_api_key=config.openai_api_key,
            openai_model=args.model or config.openai_ocr_model,
            openai_prompt=args.prompt or DEFAULT_OCR_PROMPT,
        )
    except Exception as exc:
        logger.error("OCR failed: %s", exc)
        return 1
    append_jsonl(paths["ocr"], results)
    logger.info("Generated %s OCR records (backend=%s)", len(results), backend)
    return 0


def cmd_classify(_: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("classify")
    paths = _paths(config.data_dir)
    posts = read_jsonl(paths["processed_posts"])
    ocr = read_jsonl(paths["ocr"])
    enrichments = enrich_posts(posts, ocr)
    classifications = classify_posts(posts, enrichments)
    append_jsonl(paths["enrich"], enrichments)
    append_jsonl(paths["classifications"], classifications)
    logger.info("Generated %s enrichments and %s classifications", len(enrichments), len(classifications))
    return 0


def cmd_extract_knowledge(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("extract_knowledge")
    paths = _paths(config.data_dir)
    posts = read_jsonl(paths["processed_posts"])
    ocr = read_jsonl(paths["ocr"])
    backend = args.backend
    if backend == "auto":
        backend = "openai" if config.openai_api_key else "placeholder"
    try:
        records = extract_knowledge_records(
            posts,
            ocr,
            backend=backend,
            openai_api_key=config.openai_api_key,
            model=args.model or config.openai_knowledge_model,
            max_posts=args.max_posts,
        )
    except Exception as exc:
        logger.error("Knowledge extraction failed: %s", exc)
        return 1
    append_jsonl(paths["knowledge"], records)
    logger.info("Generated %s knowledge extraction records (backend=%s)", len(records), backend)
    return 0


def cmd_qa_knowledge(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("qa_knowledge")
    paths = _paths(config.data_dir)
    input_path = Path(args.input) if args.input else paths["knowledge"]
    records = read_jsonl(input_path)
    if args.max_records is not None:
        records = records[: args.max_records]
    result = run_quality_gates_for_knowledge_records(records)

    if not args.no_write:
        write_jsonl(paths["knowledge_canonical"], result["canonical_records"])
        write_jsonl(paths["knowledge_quality_records"], result["record_reports"])
        write_json(paths["knowledge_qa_report"], result["qa_report"])

    logger.info(
        "QA knowledge processed %s records (errors=%s warnings=%s, broken_refs=%s)",
        result["qa_report"]["record_count"],
        result["qa_report"]["quality_gate_metrics"]["error_count_total"],
        result["qa_report"]["quality_gate_metrics"]["warning_count_total"],
        result["qa_report"]["quality_gate_metrics"]["broken_refs_count"],
    )
    return 0


def cmd_schema_knowledge(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("schema_knowledge")
    paths = _paths(config.data_dir)
    output_path = Path(args.output) if args.output else paths["knowledge_schema"]
    write_json(output_path, canonical_knowledge_record_json_schema())
    logger.info("Wrote canonical knowledge JSON Schema to %s", output_path)
    return 0


def _compute_or_load_knowledge_qa(paths: dict[str, Path], refresh: bool) -> tuple[list[dict], list[dict], dict]:
    canonical_records = read_jsonl(paths["knowledge_canonical"])
    quality_records = read_jsonl(paths["knowledge_quality_records"])
    qa_report = {}
    if paths["knowledge_qa_report"].exists():
        import json

        qa_report = json.loads(paths["knowledge_qa_report"].read_text(encoding="utf-8"))
    if refresh or not canonical_records or not quality_records or not qa_report:
        source_records = read_jsonl(paths["knowledge"])
        result = run_quality_gates_for_knowledge_records(source_records)
        canonical_records = result["canonical_records"]
        quality_records = result["record_reports"]
        qa_report = result["qa_report"]
        write_jsonl(paths["knowledge_canonical"], canonical_records)
        write_jsonl(paths["knowledge_quality_records"], quality_records)
        write_json(paths["knowledge_qa_report"], qa_report)
    return canonical_records, quality_records, qa_report


def _load_gate_policy(args: argparse.Namespace) -> dict:
    if getattr(args, "policy_file", None):
        return load_export_gate_policy_from_json(args.policy_file)
    return default_export_gate_policy()


def _apply_gate_threshold_overrides(policy: dict, args: argparse.Namespace) -> dict:
    policy = dict(policy)
    run_thresholds = dict(policy.get("run_thresholds") or {})
    if getattr(args, "min_evidence_resolution_rate", None) is not None:
        run_thresholds["min_evidence_resolution_rate"] = args.min_evidence_resolution_rate
    if getattr(args, "min_semantic_evidence_rate", None) is not None:
        run_thresholds["min_semantic_items_with_evidence_rate"] = args.min_semantic_evidence_rate
    if getattr(args, "max_broken_refs", None) is not None:
        run_thresholds["max_broken_refs_count"] = args.max_broken_refs
    policy["run_thresholds"] = run_thresholds
    return policy


def _compute_or_load_gate(
    paths: dict[str, Path],
    canonical_records: list[dict],
    quality_records: list[dict],
    qa_report: dict,
    *,
    policy: dict,
) -> dict:
    gate = evaluate_run_export_gate(
        canonical_records=canonical_records,
        record_reports=quality_records,
        qa_report=qa_report,
        policy=policy,
    )
    write_json(paths["knowledge_export_gate_report"], gate["gate_report"])
    write_jsonl(paths["knowledge_export_pass"], gate["accepted_records"])
    write_jsonl(paths["knowledge_export_fail"], gate["rejected_records"])
    return gate


def cmd_gate_knowledge_export(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("gate_knowledge_export")
    paths = _paths(config.data_dir)
    canonical_records, quality_records, qa_report = _compute_or_load_knowledge_qa(paths, refresh=args.refresh_qa)
    policy = _apply_gate_threshold_overrides(_load_gate_policy(args), args)
    gate = _compute_or_load_gate(paths, canonical_records, quality_records, qa_report, policy=policy)

    logger.info(
        "Knowledge export gate: run_passed=%s, accepted=%s, rejected=%s",
        gate["gate_report"]["run_gate_passed"],
        len(gate["accepted_records"]),
        len(gate["rejected_records"]),
    )
    if args.fail_on_run_gate and not gate["gate_report"]["run_gate_passed"]:
        return 1
    return 0


def cmd_export_knowledge_library(args: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("export_knowledge_library")
    paths = _paths(config.data_dir)
    canonical_records, quality_records, qa_report = _compute_or_load_knowledge_qa(paths, refresh=args.refresh_qa)
    policy = _apply_gate_threshold_overrides(_load_gate_policy(args), args)
    gate = _compute_or_load_gate(paths, canonical_records, quality_records, qa_report, policy=policy)

    export_result = export_knowledge_library_streams(
        canonical_records=canonical_records,
        record_reports=quality_records,
        gate_report=gate["gate_report"],
        schema_contract_version=args.schema_contract_version,
    )
    write_jsonl(paths["knowledge_library_ready"], export_result["ready_records"])
    write_jsonl(paths["knowledge_library_rejects"], export_result["reject_records"])
    write_json(paths["knowledge_library_export_report"], export_result["export_report"])

    logger.info(
        "Knowledge library export: ready=%s rejects=%s run_gate_passed=%s",
        export_result["export_report"]["ready_count"],
        export_result["export_report"]["reject_count"],
        export_result["export_report"]["run_gate_passed"],
    )
    if args.fail_on_run_gate and not export_result["export_report"]["run_gate_passed"]:
        return 1
    return 0


def cmd_export(_: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("export")
    paths = _paths(config.data_dir)
    count = export_dataset(config.data_dir, paths["export"])
    logger.info("Exported %s records to %s", count, paths["export"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="X legal content scraper and processing pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Collect public posts from configured X accounts")
    collect.add_argument("--account", dest="accounts", action="append", help="Source account handle (repeatable)")
    collect.add_argument("--limit", type=int, default=5, help="Max posts per account")
    collect.add_argument(
        "--backend",
        choices=[
            "auto",
            "placeholder",
            "recent",
            "timeline",
            "all",
            "x-api-recent-search",
            "x-api-user-timeline",
            "x-api-search-all",
        ],
        default="auto",
        help="Collection backend (recent search, user timeline, full archive search, or placeholder)",
    )
    collect.add_argument(
        "--mode",
        choices=["all", "filtered"],
        default="all",
        help="Collect all public posts or only posts matching tags/queries",
    )
    collect.add_argument("--tag", dest="tags", action="append", help="Tag filter, e.g. ICT or MENTORSHIP")
    collect.add_argument(
        "--query",
        dest="queries",
        action="append",
        help="Text phrase filter, e.g. 'ICT 2026 Mentorship' or 'LECTURE #1'",
    )
    collect.add_argument(
        "--match-mode",
        choices=["any", "all"],
        default="any",
        help="How multiple tag/query filters are combined",
    )
    collect.add_argument(
        "--content-mode",
        choices=["with-images", "only-text", "mixed"],
        default="mixed",
        help="Filter posts by content type",
    )
    collect.add_argument(
        "--download-images",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Download image assets and store deduplicated files under data/raw/images",
    )

    ocr = subparsers.add_parser("ocr", help="Run OCR pipeline for collected images")
    ocr.add_argument(
        "--backend",
        choices=["auto", "placeholder", "openai-vision"],
        default="auto",
        help="OCR backend",
    )
    ocr.add_argument("--model", help="Override OpenAI OCR model")
    ocr.add_argument("--prompt", help="Override OCR extraction prompt")
    extract = subparsers.add_parser("extract-knowledge", help="Generate AI-ready semantic knowledge JSON from post+OCR")
    extract.add_argument(
        "--backend",
        choices=["auto", "placeholder", "openai"],
        default="auto",
        help="Knowledge extraction backend",
    )
    extract.add_argument("--model", help="Override OpenAI knowledge extraction model")
    extract.add_argument("--max-posts", type=int, help="Limit number of posts processed in this run")
    qa = subparsers.add_parser("qa-knowledge", help="Canonicalize and validate knowledge_extract records + QA report")
    qa.add_argument("--input", help="Optional path to knowledge_extract.jsonl (default: DATA_DIR processed file)")
    qa.add_argument("--max-records", type=int, help="Limit number of records")
    qa.add_argument("--no-write", action="store_true", help="Run checks without writing output artifacts")
    schema_cmd = subparsers.add_parser("schema-knowledge", help="Export JSON Schema for canonical knowledge record")
    schema_cmd.add_argument("--output", help="Optional output path for JSON Schema")
    gate = subparsers.add_parser("gate-knowledge-export", help="Apply severity policy and export gate to canonical knowledge records")
    gate.add_argument("--refresh-qa", action="store_true", help="Recompute QA artifacts from processed/knowledge_extract.jsonl before gating")
    gate.add_argument("--policy-file", help="Optional JSON file overriding export gate policy")
    gate.add_argument("--min-evidence-resolution-rate", type=float, default=1.0, help="Run gate threshold for evidence ref resolution rate")
    gate.add_argument("--min-semantic-evidence-rate", type=float, default=1.0, help="Run gate threshold for semantic items with evidence")
    gate.add_argument("--max-broken-refs", type=int, default=0, help="Run gate threshold for broken refs")
    gate.add_argument("--fail-on-run-gate", action="store_true", help="Return non-zero exit code if run-level gate fails")
    export_lib = subparsers.add_parser("export-knowledge-library", help="Export ready/reject streams for TRADING_WORD curation")
    export_lib.add_argument("--refresh-qa", action="store_true", help="Recompute QA artifacts from processed/knowledge_extract.jsonl before export")
    export_lib.add_argument("--policy-file", help="Optional JSON file overriding export gate policy")
    export_lib.add_argument("--min-evidence-resolution-rate", type=float, default=1.0, help="Run gate threshold for evidence ref resolution rate")
    export_lib.add_argument("--min-semantic-evidence-rate", type=float, default=1.0, help="Run gate threshold for semantic items with evidence")
    export_lib.add_argument("--max-broken-refs", type=int, default=0, help="Run gate threshold for broken refs")
    export_lib.add_argument("--schema-contract-version", default="knowledge-canonical-contract-v1", help="Schema contract version tag embedded in library export")
    export_lib.add_argument("--fail-on-run-gate", action="store_true", help="Return non-zero exit code if run-level gate fails")
    subparsers.add_parser("classify", help="Run enrichment and classification")
    subparsers.add_parser("export", help="Export normalized dataset")
    return parser


def main(argv: list[str] | None = None) -> int:
    config = AppConfig.from_env()
    _configure_logging(config.log_level)
    ensure_dir(config.data_dir)

    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "collect": cmd_collect,
        "ocr": cmd_ocr,
        "extract-knowledge": cmd_extract_knowledge,
        "qa-knowledge": cmd_qa_knowledge,
        "schema-knowledge": cmd_schema_knowledge,
        "gate-knowledge-export": cmd_gate_knowledge_export,
        "export-knowledge-library": cmd_export_knowledge_library,
        "classify": cmd_classify,
        "export": cmd_export,
    }
    return handlers[args.command](args, config)


if __name__ == "__main__":
    raise SystemExit(main())

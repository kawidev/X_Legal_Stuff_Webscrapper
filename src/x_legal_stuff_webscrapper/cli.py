from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .classifier import classify_posts
from .collector_x import collect_public_posts
from .config import AppConfig
from .exporter import export_dataset
from .llm_enrichment import enrich_posts
from .storage import append_jsonl, ensure_dir, read_jsonl
from .vision_ocr import process_posts_for_ocr


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _paths(data_dir: Path) -> dict[str, Path]:
    return {
        "raw_posts": data_dir / "raw" / "posts.jsonl",
        "ocr": data_dir / "processed" / "ocr_results.jsonl",
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
    use_filters = args.mode == "filtered" or bool(tag_filters or text_filters)
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
        )
    except Exception as exc:
        logger.error("Collect failed: %s", exc)
        return 1

    append_jsonl(paths["raw_posts"], posts)
    append_jsonl(paths["processed_posts"], posts)
    logger.info(
        "Collected %s posts from %s accounts (backend=%s, mode=%s, tags=%s, queries=%s, match=%s)",
        len(posts),
        len(handles),
        backend,
        "filtered" if use_filters else "all",
        tag_filters if use_filters else [],
        text_filters if use_filters else [],
        args.match_mode,
    )
    return 0


def cmd_ocr(_: argparse.Namespace, config: AppConfig) -> int:
    logger = logging.getLogger("ocr")
    paths = _paths(config.data_dir)
    posts = read_jsonl(paths["processed_posts"])
    results = process_posts_for_ocr(posts)
    append_jsonl(paths["ocr"], results)
    logger.info("Generated %s OCR placeholder records", len(results))
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
        choices=["auto", "placeholder", "x-api-recent-search"],
        default="auto",
        help="Collection backend (official X API recent search or placeholder)",
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

    subparsers.add_parser("ocr", help="Run OCR pipeline for collected images")
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
        "classify": cmd_classify,
        "export": cmd_export,
    }
    return handlers[args.command](args, config)


if __name__ == "__main__":
    raise SystemExit(main())

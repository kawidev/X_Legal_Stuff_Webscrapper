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

    posts = collect_public_posts(handles=handles, limit_per_account=args.limit)
    append_jsonl(paths["raw_posts"], posts)
    append_jsonl(paths["processed_posts"], posts)
    logger.info("Collected %s posts from %s accounts", len(posts), len(handles))
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
    collect.add_argument("--limit", type=int, default=5, help="Max posts per account (placeholder collector)")

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

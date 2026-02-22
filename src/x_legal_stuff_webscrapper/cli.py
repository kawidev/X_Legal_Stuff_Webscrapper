from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .classifier import classify_posts
from .collector_x import collect_public_posts
from .config import AppConfig
from .exporter import export_dataset
from .llm_enrichment import enrich_posts
from .media_downloader import download_images_for_posts
from .storage import append_jsonl, ensure_dir, read_jsonl
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

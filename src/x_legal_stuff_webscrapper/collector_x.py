from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal


def _matches_filters(
    post: dict,
    *,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
) -> bool:
    tag_filters = [x.lower() for x in (tag_filters or [])]
    text_filters = [x.lower() for x in (text_filters or [])]
    if not tag_filters and not text_filters:
        return True

    haystack = f"{post.get('text', '')} {' '.join(post.get('hashtags', []))}".lower()
    checks: list[bool] = []
    checks.extend(tag in haystack for tag in tag_filters)
    checks.extend(term in haystack for term in text_filters)
    return all(checks) if match_mode == "all" else any(checks)


def collect_public_posts(
    handles: list[str],
    limit_per_account: int = 5,
    *,
    tag_filters: list[str] | None = None,
    text_filters: list[str] | None = None,
    match_mode: Literal["any", "all"] = "any",
) -> list[dict]:
    """Placeholder collector. Replace with X API or compliant ingestion backend."""
    now = datetime.now(UTC).isoformat()
    rows: list[dict] = []
    for handle in handles:
        for idx in range(limit_per_account):
            post_id = f"{handle}-{idx}"
            hashtags = ["TRADING", "ICT"] if idx % 2 == 0 else ["TRADING", "LECTURE", "MENTORSHIP"]
            text = (
                f"ICT 2026 Mentorship ... LECTURE #{idx} notes by @{handle}"
                if idx % 2
                else f"Market structure recap from @{handle}"
            )
            row = {
                "post_id": post_id,
                "author_handle": handle,
                "published_at": now,
                "scraped_at": now,
                "url": f"https://x.com/{handle}/status/{post_id}",
                "text": text,
                "hashtags": hashtags,
                "filter_context": {
                    "tag_filters": tag_filters or [],
                    "text_filters": text_filters or [],
                    "match_mode": match_mode,
                },
                "images": [
                    {
                        "image_id": f"{post_id}-img-1",
                        "source_url": f"https://example.invalid/{post_id}.jpg",
                        "file_path": None,
                    }
                ],
            }
            if _matches_filters(
                row,
                tag_filters=tag_filters,
                text_filters=text_filters,
                match_mode=match_mode,
            ):
                rows.append(row)
    return rows

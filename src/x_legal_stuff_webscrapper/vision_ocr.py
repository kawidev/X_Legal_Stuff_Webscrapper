from __future__ import annotations

from datetime import UTC, datetime


def process_posts_for_ocr(posts: list[dict]) -> list[dict]:
    """Placeholder OCR stage for image text extraction."""
    now = datetime.now(UTC).isoformat()
    results: list[dict] = []
    for post in posts:
        for image in post.get("images", []):
            results.append(
                {
                    "image_id": image["image_id"],
                    "post_id": post["post_id"],
                    "ocr_text": "",
                    "confidence": 0.0,
                    "engine": "placeholder",
                    "processed_at": now,
                }
            )
    return results

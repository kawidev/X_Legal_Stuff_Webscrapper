from __future__ import annotations

from datetime import UTC, datetime


def enrich_posts(posts: list[dict], ocr_results: list[dict]) -> list[dict]:
    """Placeholder LLM enrichment stage; intended for OpenAI API integration."""
    ocr_by_post: dict[str, list[dict]] = {}
    for item in ocr_results:
        ocr_by_post.setdefault(item["post_id"], []).append(item)

    now = datetime.now(UTC).isoformat()
    rows: list[dict] = []
    for post in posts:
        joined_ocr = " ".join(x.get("ocr_text", "") for x in ocr_by_post.get(post["post_id"], []))
        rows.append(
            {
                "entity_id": post["post_id"],
                "entity_type": "post",
                "model": "placeholder",
                "prompt_version": "v0",
                "extracted_text": joined_ocr.strip(),
                "summary": None,
                "topics": [],
                "processed_at": now,
            }
        )
    return rows

from __future__ import annotations

from datetime import UTC, datetime


def collect_public_posts(handles: list[str], limit_per_account: int = 5) -> list[dict]:
    """Placeholder collector. Replace with X API or compliant ingestion backend."""
    now = datetime.now(UTC).isoformat()
    rows: list[dict] = []
    for handle in handles:
        for idx in range(limit_per_account):
            post_id = f"{handle}-{idx}"
            rows.append(
                {
                    "post_id": post_id,
                    "author_handle": handle,
                    "published_at": now,
                    "scraped_at": now,
                    "url": f"https://x.com/{handle}/status/{post_id}",
                    "text": f"Placeholder post {idx} from @{handle}",
                    "images": [
                        {
                            "image_id": f"{post_id}-img-1",
                            "source_url": f"https://example.invalid/{post_id}.jpg",
                            "file_path": None,
                        }
                    ],
                }
            )
    return rows

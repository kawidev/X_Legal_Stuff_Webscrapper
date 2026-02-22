from __future__ import annotations

from pathlib import Path

from .storage import append_jsonl, read_jsonl


def export_dataset(data_dir: Path, output_path: Path) -> int:
    posts = read_jsonl(data_dir / "processed" / "posts.jsonl")
    classifications = read_jsonl(data_dir / "processed" / "classifications.jsonl")
    by_id = {row["entity_id"]: row for row in classifications}
    rows = []
    for post in posts:
        rows.append(
            {
                "post_id": post["post_id"],
                "author_handle": post.get("author_handle"),
                "text": post.get("text"),
                "labels": by_id.get(post["post_id"], {}).get("labels", []),
            }
        )
    return append_jsonl(output_path, rows)

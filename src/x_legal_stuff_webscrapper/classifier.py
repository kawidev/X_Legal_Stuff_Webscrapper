from __future__ import annotations

from datetime import UTC, datetime


RULES = {
    "ICT Model 2022": ["2022 model", "model 2022", "ict 2022"],
    "ICT Full Mentoring 2026": ["mentoring 2026", "full mentoring 2026"],
}


def classify_posts(posts: list[dict], enrichments: list[dict]) -> list[dict]:
    enrichment_map = {item["entity_id"]: item for item in enrichments}
    now = datetime.now(UTC).isoformat()
    rows: list[dict] = []

    for post in posts:
        text = f"{post.get('text', '')} {enrichment_map.get(post['post_id'], {}).get('extracted_text', '')}".lower()
        labels = [label for label, patterns in RULES.items() if any(pattern in text for pattern in patterns)]
        if not labels:
            labels = ["Uncategorized"]
        rows.append(
            {
                "entity_id": post["post_id"],
                "labels": labels,
                "scores": {label: 1.0 for label in labels},
                "method": "rules:v0",
                "review_status": "pending",
                "processed_at": now,
            }
        )
    return rows

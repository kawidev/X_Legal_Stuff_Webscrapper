from __future__ import annotations

from datetime import UTC, datetime

from .taxonomy_mapper import map_text_to_taxonomy


RULES = {
    "ICT Model 2022": ["2022 model", "model 2022", "ict 2022"],
    "ICT Full Mentoring 2026": ["mentoring 2026", "full mentoring 2026"],
}


def classify_posts(posts: list[dict], enrichments: list[dict]) -> list[dict]:
    enrichment_map = {item["entity_id"]: item for item in enrichments}
    now = datetime.now(UTC).isoformat()
    rows: list[dict] = []

    for post in posts:
        combined_text = f"{post.get('text', '')} {enrichment_map.get(post['post_id'], {}).get('extracted_text', '')}"
        text = combined_text.lower()
        labels = [label for label, patterns in RULES.items() if any(pattern in text for pattern in patterns)]
        taxonomy_matches = map_text_to_taxonomy(combined_text)
        labels.extend(item["label"] for item in taxonomy_matches)
        labels = list(dict.fromkeys(labels))
        if not labels:
            labels = ["Uncategorized"]
        rows.append(
            {
                "entity_id": post["post_id"],
                "labels": labels,
                "scores": {label: 1.0 for label in labels},
                "taxonomy_matches": taxonomy_matches,
                "method": "rules+taxonomy-map:v1",
                "review_status": "pending",
                "processed_at": now,
            }
        )
    return rows

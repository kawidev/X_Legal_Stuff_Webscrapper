from __future__ import annotations

import re


_LECTURE_RE = re.compile(r"\blecture\s*#\s*(\d{1,4})\b", re.IGNORECASE)
_MENTOR_2026_RE = re.compile(r"\b(?:ict\s*)?2026\s+mentorship\b", re.IGNORECASE)
_FULL_MENTOR_2026_RE = re.compile(r"\bfull\s+mentoring?\s+2026\b", re.IGNORECASE)


def map_text_to_taxonomy(text: str) -> list[dict]:
    raw_text = text or ""
    matches: list[dict] = []

    if _MENTOR_2026_RE.search(raw_text) or _FULL_MENTOR_2026_RE.search(raw_text):
        matches.append(
            {
                "rule_id": "ict_2026_mentorship_series",
                "label": "ICT Full Mentoring 2026",
                "series": "ICT 2026 Mentorship",
                "module": None,
                "lecture_number": None,
            }
        )

    for lecture_match in _LECTURE_RE.finditer(raw_text):
        lecture_number = int(lecture_match.group(1))
        matches.append(
            {
                "rule_id": "ict_lecture_number",
                "label": "ICT Full Mentoring 2026",
                "series": "ICT 2026 Mentorship",
                "module": f"Lecture #{lecture_number}",
                "lecture_number": lecture_number,
            }
        )

    deduped: list[dict] = []
    seen: set[tuple] = set()
    for item in matches:
        key = (item["rule_id"], item["label"], item["series"], item["module"], item["lecture_number"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped

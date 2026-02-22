from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

X_API_BASE_URL = "https://api.x.com/2"

CollectBackend = Literal["placeholder", "x-api-recent-search", "auto"]


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


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#")


def _quote_phrase(value: str) -> str:
    return '"' + value.strip().replace('"', '\\"') + '"'


def build_x_recent_search_query(
    *,
    handle: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
    require_images: bool = True,
) -> str:
    parts = [f"from:{handle}"]
    if require_images:
        parts.append("has:images")
    parts.append("-is:retweet")

    filter_terms: list[str] = []
    for tag in tag_filters or []:
        normalized = _normalize_tag(tag)
        if normalized:
            filter_terms.append(f"#{normalized}")
    for phrase in text_filters or []:
        phrase = phrase.strip()
        if phrase:
            filter_terms.append(_quote_phrase(phrase))

    if filter_terms:
        if match_mode == "all":
            parts.extend(filter_terms)
        else:
            parts.append("(" + " OR ".join(filter_terms) + ")")

    return " ".join(parts)


def _http_get_json(url: str, *, bearer_token: str, timeout_seconds: int = 30) -> dict:
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "User-Agent": "x-legal-stuff-webscrapper/0.1.0",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_hashtags(tweet: dict) -> list[str]:
    out: list[str] = []
    for item in ((tweet.get("entities") or {}).get("hashtags") or []):
        tag = item.get("tag")
        if tag:
            out.append(tag)
    return out


def _extract_images(tweet: dict, includes: dict) -> list[dict]:
    media_keys = ((tweet.get("attachments") or {}).get("media_keys") or [])
    media_by_key = {m.get("media_key"): m for m in includes.get("media", [])}
    images: list[dict] = []
    for key in media_keys:
        media = media_by_key.get(key)
        if not media:
            continue
        media_type = media.get("type")
        if media_type not in {"photo", "animated_gif", "video"}:
            continue
        images.append(
            {
                "image_id": key,
                "source_url": media.get("url") or media.get("preview_image_url"),
                "file_path": None,
                "media_type": media_type,
                "width": media.get("width"),
                "height": media.get("height"),
                "alt_text": media.get("alt_text"),
            }
        )
    return images


def _fetch_x_recent_search_posts_for_handle(
    *,
    handle: str,
    limit_per_account: int,
    bearer_token: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
) -> list[dict]:
    query = build_x_recent_search_query(
        handle=handle,
        tag_filters=tag_filters,
        text_filters=text_filters,
        match_mode=match_mode,
    )
    rows: list[dict] = []
    next_token: str | None = None
    fetched = 0
    page_size = min(max(limit_per_account, 10), 100)
    scraped_at = datetime.now(UTC).isoformat()

    while fetched < limit_per_account:
        params = {
            "query": query,
            "max_results": str(page_size),
            "tweet.fields": "id,text,created_at,author_id,entities,attachments,lang,public_metrics",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "media_key,type,url,preview_image_url,width,height,alt_text",
            "user.fields": "id,username,name",
        }
        if next_token:
            params["next_token"] = next_token

        url = f"{X_API_BASE_URL}/tweets/search/recent?{urlencode(params)}"
        payload = _http_get_json(url, bearer_token=bearer_token)
        includes = payload.get("includes", {})
        users_by_id = {u.get("id"): u for u in includes.get("users", [])}

        for tweet in payload.get("data", []):
            author = users_by_id.get(tweet.get("author_id"), {})
            author_handle = author.get("username") or handle
            rows.append(
                {
                    "post_id": tweet.get("id"),
                    "author_handle": author_handle,
                    "author_name": author.get("name"),
                    "published_at": tweet.get("created_at"),
                    "scraped_at": scraped_at,
                    "url": f"https://x.com/{author_handle}/status/{tweet.get('id')}",
                    "text": tweet.get("text", ""),
                    "hashtags": _extract_hashtags(tweet),
                    "lang": tweet.get("lang"),
                    "public_metrics": tweet.get("public_metrics", {}),
                    "source_backend": "x-api-recent-search",
                    "x_query": query,
                    "filter_context": {
                        "tag_filters": tag_filters or [],
                        "text_filters": text_filters or [],
                        "match_mode": match_mode,
                    },
                    "images": _extract_images(tweet, includes),
                }
            )
            fetched += 1
            if fetched >= limit_per_account:
                break

        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token or not payload.get("data"):
            break

    return rows


def _collect_placeholder_posts(
    *,
    handles: list[str],
    limit_per_account: int,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
) -> list[dict]:
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
                "source_backend": "placeholder",
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


def collect_public_posts(
    handles: list[str],
    limit_per_account: int = 5,
    *,
    backend: CollectBackend = "auto",
    x_api_bearer_token: str | None = None,
    tag_filters: list[str] | None = None,
    text_filters: list[str] | None = None,
    match_mode: Literal["any", "all"] = "any",
) -> list[dict]:
    """Collect posts via official X API recent search or fallback placeholder backend."""
    selected_backend: CollectBackend = backend
    if selected_backend == "auto":
        selected_backend = "x-api-recent-search" if x_api_bearer_token else "placeholder"

    if selected_backend == "x-api-recent-search":
        if not x_api_bearer_token:
            raise ValueError("X_API_BEARER_TOKEN is required for backend 'x-api-recent-search'")
        rows: list[dict] = []
        for handle in handles:
            rows.extend(
                _fetch_x_recent_search_posts_for_handle(
                    handle=handle,
                    limit_per_account=limit_per_account,
                    bearer_token=x_api_bearer_token,
                    tag_filters=tag_filters,
                    text_filters=text_filters,
                    match_mode=match_mode,
                )
            )
        return rows

    return _collect_placeholder_posts(
        handles=handles,
        limit_per_account=limit_per_account,
        tag_filters=tag_filters,
        text_filters=text_filters,
        match_mode=match_mode,
    )

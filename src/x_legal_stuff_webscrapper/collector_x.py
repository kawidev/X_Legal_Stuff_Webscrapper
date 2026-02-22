from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

X_API_BASE_URL = "https://api.x.com/2"
LOGGER = logging.getLogger("collector_x")

CollectBackend = Literal[
    "placeholder",
    "recent",
    "timeline",
    "all",
    "x-api-recent-search",
    "x-api-user-timeline",
    "x-api-search-all",
    "auto",
]
ContentMode = Literal["with-images", "only-text", "mixed"]


def _normalize_backend(backend: str) -> str:
    aliases = {
        "x-api-recent-search": "recent",
        "x-api-user-timeline": "timeline",
        "x-api-search-all": "all",
    }
    return aliases.get(backend, backend)


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


def _matches_content_mode(post: dict, content_mode: ContentMode) -> bool:
    has_images = bool(post.get("images"))
    if content_mode == "mixed":
        return True
    if content_mode == "with-images":
        return has_images
    return not has_images


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#")


def _quote_phrase(value: str) -> str:
    return '"' + value.strip().replace('"', '\\"') + '"'


def build_x_search_query(
    *,
    handle: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
    content_mode: ContentMode,
) -> str:
    parts = [f"from:{handle}"]
    if content_mode == "with-images":
        parts.append("has:images")
    elif content_mode == "only-text":
        # X query operators vary by media type; `-has:images` catches image posts.
        # Final filtering is also enforced locally for consistency across backends.
        parts.append("-has:images")

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
    max_attempts = 4
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Accept": "application/json",
            "User-Agent": "x-legal-stuff-webscrapper/0.1.0",
        },
        method="GET",
    )
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(req, timeout=timeout_seconds) as response:
                headers = response.headers
                LOGGER.info(
                    "X API response %s (limit=%s remaining=%s reset=%s)",
                    response.status,
                    headers.get("x-rate-limit-limit"),
                    headers.get("x-rate-limit-remaining"),
                    headers.get("x-rate-limit-reset"),
                )
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            headers = exc.headers or {}
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""

            LOGGER.warning(
                "X API HTTPError %s on attempt %s/%s (limit=%s remaining=%s reset=%s) url=%s",
                exc.code,
                attempt,
                max_attempts,
                headers.get("x-rate-limit-limit"),
                headers.get("x-rate-limit-remaining"),
                headers.get("x-rate-limit-reset"),
                url.split("?")[0],
            )

            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == max_attempts:
                raise RuntimeError(
                    f"X API request failed with HTTP {exc.code}. "
                    f"Body preview: {body[:300]}"
                ) from exc

            reset_value = headers.get("x-rate-limit-reset")
            sleep_seconds = min(2 ** (attempt - 1), 30)
            if reset_value and str(reset_value).isdigit():
                reset_epoch = int(str(reset_value))
                wait_until_reset = max(0, reset_epoch - int(time.time()))
                if wait_until_reset > 0:
                    sleep_seconds = min(wait_until_reset + 1, 60)
            time.sleep(sleep_seconds)
        except URLError as exc:
            LOGGER.warning("X API URLError on attempt %s/%s: %s", attempt, max_attempts, exc)
            if attempt == max_attempts:
                raise RuntimeError(f"X API network request failed: {exc}") from exc
            time.sleep(min(2 ** (attempt - 1), 15))

    raise RuntimeError("Unreachable X API request state")


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


def _build_post_row(
    *,
    tweet: dict,
    includes: dict,
    author_handle: str,
    author_name: str | None,
    source_backend: str,
    scraped_at: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
    content_mode: ContentMode,
    x_query: str | None = None,
) -> dict:
    row = {
        "post_id": tweet.get("id"),
        "author_handle": author_handle,
        "author_name": author_name,
        "published_at": tweet.get("created_at"),
        "scraped_at": scraped_at,
        "url": f"https://x.com/{author_handle}/status/{tweet.get('id')}",
        "text": tweet.get("text", ""),
        "hashtags": _extract_hashtags(tweet),
        "lang": tweet.get("lang"),
        "public_metrics": tweet.get("public_metrics", {}),
        "source_backend": source_backend,
        "filter_context": {
            "tag_filters": tag_filters or [],
            "text_filters": text_filters or [],
            "match_mode": match_mode,
            "content_mode": content_mode,
        },
        "images": _extract_images(tweet, includes),
    }
    if x_query is not None:
        row["x_query"] = x_query
    return row


def _search_endpoint_path(search_backend: str) -> str:
    if search_backend == "recent":
        return "/tweets/search/recent"
    if search_backend == "all":
        return "/tweets/search/all"
    raise ValueError(f"Unsupported search backend: {search_backend}")


def _fetch_x_search_posts_for_handle(
    *,
    search_backend: Literal["recent", "all"],
    handle: str,
    limit_per_account: int,
    bearer_token: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
    content_mode: ContentMode,
) -> list[dict]:
    query = build_x_search_query(
        handle=handle,
        tag_filters=tag_filters,
        text_filters=text_filters,
        match_mode=match_mode,
        content_mode=content_mode,
    )
    rows: list[dict] = []
    next_token: str | None = None
    page_size = min(max(limit_per_account, 10), 100)
    scraped_at = datetime.now(UTC).isoformat()
    endpoint_path = _search_endpoint_path(search_backend)

    while len(rows) < limit_per_account:
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

        url = f"{X_API_BASE_URL}{endpoint_path}?{urlencode(params)}"
        payload = _http_get_json(url, bearer_token=bearer_token)
        includes = payload.get("includes", {})
        users_by_id = {u.get("id"): u for u in includes.get("users", [])}

        for tweet in payload.get("data", []):
            author = users_by_id.get(tweet.get("author_id"), {})
            row = _build_post_row(
                tweet=tweet,
                includes=includes,
                author_handle=author.get("username") or handle,
                author_name=author.get("name"),
                source_backend=f"x-api-search-{search_backend}",
                scraped_at=scraped_at,
                tag_filters=tag_filters,
                text_filters=text_filters,
                match_mode=match_mode,
                content_mode=content_mode,
                x_query=query,
            )
            if _matches_content_mode(row, content_mode):
                rows.append(row)
            if len(rows) >= limit_per_account:
                break

        meta = payload.get("meta") or {}
        next_token = meta.get("next_token")
        if not next_token or not payload.get("data"):
            break

    return rows


def _get_x_user_by_username(*, handle: str, bearer_token: str) -> dict:
    url = (
        f"{X_API_BASE_URL}/users/by/username/{quote(handle)}?"
        + urlencode({"user.fields": "id,name,username"})
    )
    payload = _http_get_json(url, bearer_token=bearer_token)
    data = payload.get("data")
    if not data:
        raise ValueError(f"User not found in X API: {handle}")
    return data


def _fetch_x_timeline_posts_for_handle(
    *,
    handle: str,
    limit_per_account: int,
    bearer_token: str,
    tag_filters: list[str] | None,
    text_filters: list[str] | None,
    match_mode: Literal["any", "all"],
    content_mode: ContentMode,
) -> list[dict]:
    user = _get_x_user_by_username(handle=handle, bearer_token=bearer_token)
    user_id = user["id"]
    author_handle = user.get("username", handle)
    author_name = user.get("name")
    rows: list[dict] = []
    next_token: str | None = None
    page_size = min(max(limit_per_account, 10), 100)
    scraped_at = datetime.now(UTC).isoformat()

    while len(rows) < limit_per_account:
        params = {
            "max_results": str(page_size),
            "tweet.fields": "id,text,created_at,entities,attachments,lang,public_metrics",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,width,height,alt_text",
        }
        if next_token:
            params["pagination_token"] = next_token

        url = f"{X_API_BASE_URL}/users/{user_id}/tweets?{urlencode(params)}"
        payload = _http_get_json(url, bearer_token=bearer_token)
        includes = payload.get("includes", {})
        for tweet in payload.get("data", []):
            row = _build_post_row(
                tweet=tweet,
                includes=includes,
                author_handle=author_handle,
                author_name=author_name,
                source_backend="x-api-user-timeline",
                scraped_at=scraped_at,
                tag_filters=tag_filters,
                text_filters=text_filters,
                match_mode=match_mode,
                content_mode=content_mode,
                x_query=None,
            )
            if not _matches_content_mode(row, content_mode):
                continue
            if not _matches_filters(
                row,
                tag_filters=tag_filters,
                text_filters=text_filters,
                match_mode=match_mode,
            ):
                continue
            rows.append(row)
            if len(rows) >= limit_per_account:
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
    content_mode: ContentMode,
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
            images = (
                []
                if idx % 3 == 0
                else [
                    {
                        "image_id": f"{post_id}-img-1",
                        "source_url": f"https://example.invalid/{post_id}.jpg",
                        "file_path": None,
                    }
                ]
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
                    "content_mode": content_mode,
                },
                "images": images,
            }
            if not _matches_content_mode(row, content_mode):
                continue
            if not _matches_filters(
                row,
                tag_filters=tag_filters,
                text_filters=text_filters,
                match_mode=match_mode,
            ):
                continue
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
    content_mode: ContentMode = "mixed",
) -> list[dict]:
    """Collect posts using X API backends (`recent`, `timeline`, `all`) or placeholder."""
    selected_backend = _normalize_backend(backend)
    if selected_backend == "auto":
        selected_backend = "timeline" if x_api_bearer_token else "placeholder"

    if selected_backend in {"recent", "all", "timeline"}:
        if not x_api_bearer_token:
            raise ValueError(f"X_API_BEARER_TOKEN is required for backend '{selected_backend}'")

    if selected_backend in {"recent", "all"}:
        rows: list[dict] = []
        for handle in handles:
            rows.extend(
                _fetch_x_search_posts_for_handle(
                    search_backend=selected_backend,
                    handle=handle,
                    limit_per_account=limit_per_account,
                    bearer_token=x_api_bearer_token or "",
                    tag_filters=tag_filters,
                    text_filters=text_filters,
                    match_mode=match_mode,
                    content_mode=content_mode,
                )
            )
        return rows

    if selected_backend == "timeline":
        rows = []
        for handle in handles:
            rows.extend(
                _fetch_x_timeline_posts_for_handle(
                    handle=handle,
                    limit_per_account=limit_per_account,
                    bearer_token=x_api_bearer_token or "",
                    tag_filters=tag_filters,
                    text_filters=text_filters,
                    match_mode=match_mode,
                    content_mode=content_mode,
                )
            )
        return rows

    return _collect_placeholder_posts(
        handles=handles,
        limit_per_account=limit_per_account,
        tag_filters=tag_filters,
        text_filters=text_filters,
        match_mode=match_mode,
        content_mode=content_mode,
    )

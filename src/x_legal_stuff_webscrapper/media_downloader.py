from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .storage import ensure_dir


def _guess_extension(source_url: str, content_type: str | None) -> str:
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    suffix = Path(urlparse(source_url).path).suffix
    return suffix if suffix else ".bin"


def _download_bytes(source_url: str, timeout_seconds: int = 30) -> tuple[bytes, str | None]:
    req = Request(
        source_url,
        headers={
            "User-Agent": "x-legal-stuff-webscrapper/0.1.0",
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_seconds) as response:
        return response.read(), response.headers.get("Content-Type")


def _store_blob_dedup(root: Path, blob: bytes, source_url: str, content_type: str | None) -> tuple[Path, str]:
    sha256 = hashlib.sha256(blob).hexdigest()
    ext = _guess_extension(source_url, content_type)
    target_dir = ensure_dir(root / "by_sha256")
    target_path = target_dir / f"{sha256}{ext.lower()}"
    if not target_path.exists():
        target_path.write_bytes(blob)
    return target_path, sha256


def download_images_for_posts(
    posts: list[dict],
    *,
    data_dir: Path,
    timeout_seconds: int = 30,
) -> tuple[list[dict], list[dict]]:
    """
    Download images referenced in posts and update image metadata in-place.

    Returns:
      (updated_posts, manifest_rows)
    """
    images_root = ensure_dir(data_dir / "raw" / "images")
    manifest_rows: list[dict] = []
    processed_urls: dict[str, dict] = {}
    now = datetime.now(UTC).isoformat()

    for post in posts:
        for image in post.get("images", []):
            source_url = image.get("source_url")
            if not source_url:
                image["download_status"] = "missing_url"
                continue

            if source_url in processed_urls:
                cached = processed_urls[source_url]
                image.update(cached)
                continue

            try:
                blob, content_type = _download_bytes(source_url, timeout_seconds=timeout_seconds)
                local_path, sha256 = _store_blob_dedup(images_root, blob, source_url, content_type)
                relative_path = local_path.relative_to(data_dir).as_posix()
                update = {
                    "file_path": relative_path,
                    "sha256": sha256,
                    "file_size": len(blob),
                    "content_type": content_type,
                    "download_status": "downloaded",
                    "downloaded_at": now,
                }
                image.update(update)
                processed_urls[source_url] = update
                manifest_rows.append(
                    {
                        "image_id": image.get("image_id"),
                        "post_id": post.get("post_id"),
                        "source_url": source_url,
                        "file_path": relative_path,
                        "sha256": sha256,
                        "file_size": len(blob),
                        "content_type": content_type,
                        "download_status": "downloaded",
                        "downloaded_at": now,
                    }
                )
            except Exception as exc:
                error_info = {
                    "download_status": "error",
                    "download_error": str(exc),
                    "downloaded_at": now,
                }
                image.update(error_info)
                processed_urls[source_url] = error_info
                manifest_rows.append(
                    {
                        "image_id": image.get("image_id"),
                        "post_id": post.get("post_id"),
                        "source_url": source_url,
                        "download_status": "error",
                        "download_error": str(exc),
                        "downloaded_at": now,
                    }
                )

    return posts, manifest_rows

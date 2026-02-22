from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen


OcrBackend = Literal["placeholder", "openai-vision", "auto"]

DEFAULT_OCR_PROMPT = (
    "Extract all visible text from this trading-related image. "
    "Preserve headings, bullets, labels, and lecture numbering if present. "
    "Return transcription-like output without summarizing."
)


def _guess_mime_type(file_path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(file_path.suffix.lower(), "application/octet-stream")


def _image_file_to_data_uri(file_path: Path) -> str:
    mime_type = _guess_mime_type(file_path)
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_openai_chat_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return ""


def _openai_vision_ocr(
    *,
    image_path: Path,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: int = 90,
) -> dict:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": _image_file_to_data_uri(image_path)}},
                ],
            }
        ],
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    return {
        "ocr_text": _extract_openai_chat_text(response_payload),
        "raw_response_id": response_payload.get("id"),
        "usage": response_payload.get("usage"),
    }


def process_posts_for_ocr(
    posts: list[dict],
    *,
    data_dir: Path | None = None,
    backend: OcrBackend = "auto",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
    openai_prompt: str = DEFAULT_OCR_PROMPT,
) -> list[dict]:
    """OCR stage for image text extraction."""
    selected_backend: OcrBackend = backend
    if selected_backend == "auto":
        selected_backend = "openai-vision" if openai_api_key else "placeholder"

    now = datetime.now(UTC).isoformat()
    results: list[dict] = []
    for post in posts:
        for image in post.get("images", []):
            base_row = {
                "image_id": image["image_id"],
                "post_id": post["post_id"],
                "processed_at": now,
            }

            if selected_backend == "openai-vision":
                if not openai_api_key:
                    raise ValueError("OPENAI_API_KEY is required for backend 'openai-vision'")
                if data_dir is None:
                    raise ValueError("data_dir is required for backend 'openai-vision'")

                file_path_value = image.get("file_path")
                if not file_path_value:
                    results.append(
                        {
                            **base_row,
                            "ocr_text": "",
                            "confidence": 0.0,
                            "engine": "openai-vision",
                            "model": openai_model,
                            "status": "skipped_no_local_file",
                        }
                    )
                    continue

                image_path = (data_dir / file_path_value).resolve()
                if not image_path.exists():
                    results.append(
                        {
                            **base_row,
                            "ocr_text": "",
                            "confidence": 0.0,
                            "engine": "openai-vision",
                            "model": openai_model,
                            "status": "missing_local_file",
                            "file_path": file_path_value,
                        }
                    )
                    continue

                try:
                    ocr_output = _openai_vision_ocr(
                        image_path=image_path,
                        api_key=openai_api_key,
                        model=openai_model,
                        prompt=openai_prompt,
                    )
                    results.append(
                        {
                            **base_row,
                            "ocr_text": ocr_output.get("ocr_text", ""),
                            "confidence": None,
                            "engine": "openai-vision",
                            "model": openai_model,
                            "status": "processed",
                            "file_path": file_path_value,
                            "raw_response_id": ocr_output.get("raw_response_id"),
                            "usage": ocr_output.get("usage"),
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            **base_row,
                            "ocr_text": "",
                            "confidence": 0.0,
                            "engine": "openai-vision",
                            "model": openai_model,
                            "status": "error",
                            "file_path": file_path_value,
                            "error": str(exc),
                        }
                    )
                continue

            results.append(
                {
                    **base_row,
                    "ocr_text": "",
                    "confidence": 0.0,
                    "engine": "placeholder",
                    "status": "processed",
                }
            )
    return results

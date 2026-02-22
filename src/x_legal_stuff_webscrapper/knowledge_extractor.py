from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("knowledge_extractor")

ExtractionBackend = Literal["placeholder", "openai", "auto"]
PIPELINE_VERSION = "knowledge-extractor-v1"
PROMPT_VERSION = "knowledge-json-v1"

SYSTEM_PROMPT = """
Jestes modułem pozyskiwania i wstepnej obrobki wiedzy tradingowej z X oraz materialow obrazkowych.
Nie tworz kanonu. Dostarczaj material wejsciowy do dalszej kuracji.

ZASADY:
- Oddzielaj fakty od interpretacji: observed / inferred / uncertain.
- Zachowuj provenance poprzez evidence_refs odnoszace sie do provided provenance_index.
- Minimalizuj halucynacje: jesli brak danych, zwroc unknown / uncertain.
- Glowny artefakt ma byc JSON.

Wypelnij ponizsze sekcje na podstawie wejscia:
- raw_capture.image_descriptions
- knowledge_extract
- trading_context_extract
- contextor_mapping_candidates
- quality_control
- optional human_review_summary

Nie zmieniaj znaczenia przekazanych danych z source_bundle/raw_capture/provenance_index.
Zachowaj stabilne nazwy pol i zwroc poprawny JSON object.
""".strip()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _infer_language(texts: list[str]) -> str:
    joined = " ".join(t for t in texts if t).strip()
    if not joined:
        return "unknown"
    lowered = joined.lower()
    has_pl = any(ch in joined for ch in "ąćęłńóśźż")
    # Very rough heuristic for English markers in OCR/post text.
    english_markers = (" the ", " and ", "what ", "price ", "chart ", "liquidity ", "entry ")
    has_en = any(marker in lowered for marker in english_markers)
    if has_pl and has_en:
        return "mixed"
    if has_pl:
        return "pl"
    return "en"


def _ocr_quality(ocr_row: dict) -> str:
    if ocr_row.get("status") != "processed":
        return "low"
    text = (ocr_row.get("ocr_text") or "").strip()
    if len(text) >= 500:
        return "high"
    if len(text) >= 80:
        return "medium"
    return "low"


def _build_provenance_index(post: dict, ocr_rows: list[dict]) -> list[dict]:
    refs: list[dict] = []
    post_text = (post.get("text") or "").strip()
    refs.append(
        {
            "ref_id": f"post:{post.get('post_id')}:text",
            "type": "post_text",
            "source_post_id": post.get("post_id"),
            "image_id": None,
            "excerpt": post_text[:280],
        }
    )
    for row in ocr_rows:
        refs.append(
            {
                "ref_id": f"ocr:{row.get('image_id')}",
                "type": "ocr",
                "source_post_id": row.get("post_id"),
                "image_id": row.get("image_id"),
                "excerpt": (row.get("ocr_text") or row.get("error") or "")[:280],
            }
        )
    return refs


def _build_raw_capture(post: dict, ocr_rows: list[dict]) -> dict:
    image_descriptions = []
    for image in post.get("images", []):
        image_descriptions.append(
            {
                "image_id": image.get("image_id"),
                "observed_visual_elements": [],
                "chart_timeframe": None,
                "instrument_hint": None,
                "confidence": 0.0,
            }
        )
    return {
        "text_exact": [post.get("text", "")],
        "ocr_text": [
            {
                "image_id": row.get("image_id"),
                "text": row.get("ocr_text", "") or "",
                "quality": _ocr_quality(row),
            }
            for row in ocr_rows
        ],
        "image_descriptions": image_descriptions,
    }


def _base_output(*, post: dict, ocr_rows: list[dict], run_id: str) -> dict:
    texts_for_lang = [post.get("text", "")] + [row.get("ocr_text", "") or "" for row in ocr_rows]
    source_type = "mixed" if ocr_rows else "x_post"
    return {
        "job_meta": {
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_id,
            "created_at_utc": _now_iso(),
            "source_type": source_type,
            "status": "partial" if any(r.get("status") != "processed" for r in ocr_rows) else "ok",
        },
        "source_bundle": {
            "platform": "X",
            "author_handle": post.get("author_handle"),
            "author_display_name": post.get("author_name"),
            "post_ids": [post.get("post_id")],
            "post_urls": [post.get("url")],
            "timestamps_utc": [post.get("published_at")],
            "language": _infer_language(texts_for_lang),
        },
        "raw_capture": _build_raw_capture(post, ocr_rows),
        "knowledge_extract": {
            "terms_detected": [],
            "definitions_candidate": [],
            "relations_candidate": [],
            "variants_candidate": [],
            "contradictions_or_ambiguities": [],
        },
        "trading_context_extract": {
            "htf_elements": [],
            "ltf_elements": [],
            "time_windows_mentioned": [],
            "poi_elements": [],
            "liquidity_elements": [],
            "execution_elements": [],
            "invalidation_elements": [],
            "outcome_elements": [],
        },
        "contextor_mapping_candidates": {
            "potential_events": [],
            "potential_questions": [],
            "potential_play_candidates": [],
        },
        "quality_control": {
            "missing_data": [],
            "uncertainties": [],
            "possible_hallucination_risks": [],
            "needs_human_review": True,
        },
        "provenance_index": _build_provenance_index(post, ocr_rows),
    }


def _call_openai_json(*, api_key: str, model: str, system_prompt: str, user_payload: dict, timeout_seconds: int = 120) -> dict:
    body = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices for knowledge extraction")
    content = ((choices[0] or {}).get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI returned empty content for knowledge extraction")
    parsed = json.loads(content)
    parsed["_openai_meta"] = {
        "id": payload.get("id"),
        "usage": payload.get("usage"),
        "model": payload.get("model"),
    }
    return parsed


def _merge_sections(base: dict, model_output: dict) -> dict:
    merged = json.loads(json.dumps(base))  # deep copy via JSON-safe structure
    for key in [
        "raw_capture",
        "knowledge_extract",
        "trading_context_extract",
        "contextor_mapping_candidates",
        "quality_control",
        "human_review_summary",
    ]:
        if key in model_output:
            if isinstance(merged.get(key), dict) and isinstance(model_output.get(key), dict):
                merged[key].update(model_output[key])
            else:
                merged[key] = model_output[key]

    # Preserve base immutable provenance/source metadata; allow optional refinements only where safe.
    merged["job_meta"]["status"] = model_output.get("job_meta", {}).get("status", merged["job_meta"]["status"])
    return merged


def _placeholder_enrichment(base: dict) -> dict:
    base["quality_control"]["missing_data"].append("knowledge_extraction_backend_not_configured")
    base["quality_control"]["uncertainties"].append("No semantic extraction performed; placeholder output only.")
    base["job_meta"]["status"] = "partial"
    return base


def extract_knowledge_records(
    posts: list[dict],
    ocr_results: list[dict],
    *,
    backend: ExtractionBackend = "auto",
    openai_api_key: str | None = None,
    model: str = "gpt-4.1-mini",
    max_posts: int | None = None,
) -> list[dict]:
    selected_backend: ExtractionBackend = backend
    if selected_backend == "auto":
        selected_backend = "openai" if openai_api_key else "placeholder"

    ocr_by_post: dict[str, list[dict]] = {}
    for row in ocr_results:
        ocr_by_post.setdefault(str(row.get("post_id")), []).append(row)

    outputs: list[dict] = []
    for idx, post in enumerate(posts):
        if max_posts is not None and idx >= max_posts:
            break
        post_id = str(post.get("post_id"))
        related_ocr = ocr_by_post.get(post_id, [])
        run_id = f"{post_id}-{uuid.uuid4().hex[:8]}"
        base = _base_output(post=post, ocr_rows=related_ocr, run_id=run_id)
        base["job_meta"]["prompt_version"] = PROMPT_VERSION

        if selected_backend == "placeholder":
            outputs.append(_placeholder_enrichment(base))
            continue
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for backend 'openai'")

        user_payload = {
            "task": "Fill semantic extraction sections using observed source data only; preserve uncertainty.",
            "schema_note": "Return JSON object with sections matching the provided base skeleton keys.",
            "input_record": base,
        }
        try:
            model_output = _call_openai_json(
                api_key=openai_api_key,
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_payload=user_payload,
            )
            final = _merge_sections(base, model_output)
            final["job_meta"]["status"] = "ok"
            if "_openai_meta" in model_output:
                final["job_meta"]["openai_response_id"] = model_output["_openai_meta"].get("id")
                final["job_meta"]["openai_model"] = model_output["_openai_meta"].get("model")
                final["job_meta"]["usage"] = model_output["_openai_meta"].get("usage")
            outputs.append(final)
        except Exception as exc:
            LOGGER.error("Knowledge extraction failed for post_id=%s: %s", post_id, exc)
            base["job_meta"]["status"] = "failed"
            base["quality_control"]["missing_data"].append("knowledge_extract_generation_failed")
            base["quality_control"]["uncertainties"].append(str(exc))
            base["quality_control"]["possible_hallucination_risks"].append(
                "No model output due to extraction failure; downstream semantic fields remain empty."
            )
            outputs.append(base)
    return outputs

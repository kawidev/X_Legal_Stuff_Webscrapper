from x_legal_stuff_webscrapper.knowledge_extractor import _base_output, _infer_language


def test_infer_language_detects_mixed() -> None:
    value = _infer_language(["This is price action", "To jest test założeń"])
    assert value == "mixed"


def test_base_output_contains_schema_roots() -> None:
    post = {
        "post_id": "p1",
        "author_handle": "demo",
        "author_name": "Demo",
        "published_at": "2026-01-01T00:00:00Z",
        "url": "https://x.com/demo/status/p1",
        "text": "IFVG Masterclass",
        "images": [{"image_id": "img1"}],
    }
    ocr_rows = [
        {
            "post_id": "p1",
            "image_id": "img1",
            "ocr_text": "IFVG explained " * 40,
            "status": "processed",
        }
    ]
    result = _base_output(post=post, ocr_rows=ocr_rows, run_id="run1")

    for key in [
        "job_meta",
        "source_bundle",
        "raw_capture",
        "knowledge_extract",
        "trading_context_extract",
        "contextor_mapping_candidates",
        "quality_control",
        "provenance_index",
    ]:
        assert key in result
    assert result["source_bundle"]["post_ids"] == ["p1"]
    assert result["raw_capture"]["ocr_text"][0]["quality"] == "medium" or result["raw_capture"]["ocr_text"][0]["quality"] == "high"

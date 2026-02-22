from x_legal_stuff_webscrapper.classifier import classify_posts


def test_classifier_matches_ict_model_2022_rule() -> None:
    posts = [
        {
            "post_id": "p1",
            "text": "This note explains ICT 2022 model on EURUSD",
        }
    ]
    enrichments = [{"entity_id": "p1", "extracted_text": ""}]

    results = classify_posts(posts, enrichments)

    assert results[0]["entity_id"] == "p1"
    assert "ICT Model 2022" in results[0]["labels"]

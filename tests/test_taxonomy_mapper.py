from x_legal_stuff_webscrapper.taxonomy_mapper import map_text_to_taxonomy


def test_taxonomy_mapper_detects_mentorship_and_lecture() -> None:
    matches = map_text_to_taxonomy("ICT 2026 Mentorship ... LECTURE #12 notes")

    labels = [item["label"] for item in matches]
    modules = [item["module"] for item in matches if item["module"]]

    assert "ICT Full Mentoring 2026" in labels
    assert "Lecture #12" in modules

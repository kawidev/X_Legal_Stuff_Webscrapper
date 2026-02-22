from x_legal_stuff_webscrapper.vision_ocr import _extract_openai_chat_text


def test_extract_openai_chat_text_from_string_content() -> None:
    payload = {"choices": [{"message": {"content": "line 1\nline 2"}}]}
    assert _extract_openai_chat_text(payload) == "line 1\nline 2"


def test_extract_openai_chat_text_from_list_content() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "output_text", "text": "Hello"},
                        {"type": "output_text", "text": "World"},
                    ]
                }
            }
        ]
    }
    assert _extract_openai_chat_text(payload) == "Hello\nWorld"

from x_legal_stuff_webscrapper.cli import build_parser


def test_cli_has_expected_subcommands() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--account", "example", "--limit", "2"])

    assert namespace.command == "collect"
    assert namespace.accounts == ["example"]
    assert namespace.limit == 2
    assert namespace.backend == "auto"
    assert namespace.content_mode == "mixed"
    assert namespace.download_images is False


def test_cli_collect_supports_filter_args() -> None:
    parser = build_parser()
    namespace = parser.parse_args(
        [
            "collect",
            "--mode",
            "filtered",
            "--tag",
            "ICT",
            "--query",
            "ICT 2026 Mentorship",
            "--match-mode",
            "all",
        ]
    )

    assert namespace.mode == "filtered"
    assert namespace.tags == ["ICT"]
    assert namespace.queries == ["ICT 2026 Mentorship"]
    assert namespace.match_mode == "all"
    assert namespace.content_mode == "mixed"
    assert namespace.download_images is False


def test_cli_collect_supports_backend_option() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--backend", "timeline"])

    assert namespace.backend == "timeline"


def test_cli_collect_supports_download_images_toggle() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--download-images"])

    assert namespace.download_images is True


def test_cli_collect_supports_content_mode_option() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--content-mode", "with-images"])

    assert namespace.content_mode == "with-images"


def test_cli_ocr_supports_backend_and_model() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["ocr", "--backend", "openai-vision", "--model", "gpt-4.1-mini"])

    assert namespace.command == "ocr"
    assert namespace.backend == "openai-vision"
    assert namespace.model == "gpt-4.1-mini"

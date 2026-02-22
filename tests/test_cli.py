from x_legal_stuff_webscrapper.cli import build_parser


def test_cli_has_expected_subcommands() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--account", "example", "--limit", "2"])

    assert namespace.command == "collect"
    assert namespace.accounts == ["example"]
    assert namespace.limit == 2
    assert namespace.backend == "auto"


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


def test_cli_collect_supports_backend_option() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--backend", "x-api-recent-search"])

    assert namespace.backend == "x-api-recent-search"

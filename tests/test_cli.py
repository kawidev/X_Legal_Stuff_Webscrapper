from x_legal_stuff_webscrapper.cli import build_parser


def test_cli_has_expected_subcommands() -> None:
    parser = build_parser()
    namespace = parser.parse_args(["collect", "--account", "example", "--limit", "2"])

    assert namespace.command == "collect"
    assert namespace.accounts == ["example"]
    assert namespace.limit == 2

import voicetype.__main__ as entrypoint
from voicetype.cli import build_parser


def test_python_module_entrypoint_exposes_main():
    assert callable(entrypoint.main)


def test_cli_has_listen_command():
    parser = build_parser()

    args = parser.parse_args(["listen", "--no-llm", "--no-paste"])

    assert args.command == "listen"
    assert args.no_llm is True
    assert args.no_paste is True

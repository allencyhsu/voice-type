import voicetype.__main__ as entrypoint
from voicetype.cli import build_parser, describe_pipeline_result
from voicetype.pipeline import PipelineResult


def test_python_module_entrypoint_exposes_main():
    assert callable(entrypoint.main)


def test_cli_has_listen_command():
    parser = build_parser()

    args = parser.parse_args(["listen", "--no-llm", "--no-paste"])

    assert args.command == "listen"
    assert args.no_llm is True
    assert args.no_paste is True


def test_describe_pipeline_result_explains_empty_transcript():
    message = describe_pipeline_result(
        PipelineResult(
            status="empty_transcript",
            raw_text="",
            final_text="",
            language="zh",
            duration=1.2,
            transcribe_time=0.3,
        )
    )

    assert "No text recognized" in message
    assert "status=empty_transcript" in message
    assert "language=zh" in message

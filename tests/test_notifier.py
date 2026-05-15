from voicetype.notifier import ConsoleNotifier


def test_console_notifier_prints_prefixed_status(capsys):
    notifier = ConsoleNotifier()

    notifier.notify("Listening")

    assert capsys.readouterr().out == "[VoiceType] Listening\n"

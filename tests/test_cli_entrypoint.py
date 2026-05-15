import voicetype.__main__ as entrypoint


def test_python_module_entrypoint_exposes_main():
    assert callable(entrypoint.main)

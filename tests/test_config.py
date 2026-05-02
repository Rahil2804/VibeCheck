import os
from pathlib import Path

from backend.config import load_environment


def test_load_environment_reads_env_file(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOURCE_TIMEOUT_SECONDS", raising=False)

    load_environment(Path("tests/fixtures/sample.env"))

    assert os.environ["OPENAI_API_KEY"] == "test-openai-key"
    assert os.environ["SOURCE_TIMEOUT_SECONDS"] == "3"

import re
from pathlib import Path

import pytest

from app.core.config import ApiConfig

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
JSON_VALUE = re.compile(r"^[A-Z_]+=['\"]?[\[{]")


def test_json_values_are_single_quoted():
    # `just` (dotenv-load) removes the double quotes of an unquoted value and breaks the JSON.
    lines = [line.lstrip("# ") for line in ENV_EXAMPLE.read_text().splitlines()]
    json_lines = [line for line in lines if JSON_VALUE.match(line)]
    unquoted = [line for line in json_lines if not line.split("=", 1)[1].startswith("'")]
    assert json_lines
    assert unquoted == []


def test_settings_parse_the_example(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORS_ORIGINS")  # tests/conftest.py sets it; the file must win here

    config = ApiConfig(_env_file=ENV_EXAMPLE)  # type: ignore[call-arg]  # pydantic-settings init option

    assert config.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]

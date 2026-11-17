import ast

import pytest

from tests.architecture.source import APP_DIR, python_files

# Log ids and counts. These fields carry secrets or personal data.
FORBIDDEN_FIELDS = {
    "api_key",
    "authorization",
    "body",
    "cookie",
    "email",
    "password",
    "phone",
    "prompt",
    "secret",
    "token",
}
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "bind_context"
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "log"
        and func.attr in LOG_METHODS
    )


def _forbidden_fields(source: str) -> list[tuple[int, str | None]]:
    return [
        (node.lineno, keyword.arg)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _is_log_call(node)
        for keyword in node.keywords
        if keyword.arg in FORBIDDEN_FIELDS
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('log.info("login_failed", email=email)', [(1, "email")]),
        ("bind_context(token=token)", [(1, "token")]),
        ('log.info("login_failed", user_id=user_id)', []),
        ("send_mail(email=email)", []),
    ],
    ids=["log_call", "bind_context", "ids_only", "not_a_log_call"],
)
def test_finds_forbidden_fields_only_in_log_calls(source: str, expected: list[tuple[int, str]]):
    assert _forbidden_fields(source) == expected


def test_logs_carry_no_secrets_or_personal_data():
    offenders = [
        f"{path.relative_to(APP_DIR)}:{line} {field}"
        for path in python_files(APP_DIR)
        for line, field in _forbidden_fields(path.read_text())
    ]
    assert offenders == []

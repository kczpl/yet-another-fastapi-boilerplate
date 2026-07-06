import re
from pathlib import Path

from app.core.errors import ERRORS

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_RAISE_CALL = re.compile(
    r"raise_(?:not_found|bad_request|unauthorized|forbidden|conflict|validation_error|server_error)"
    r"\(\s*['\"]([^'\"]+)['\"]"
)
_APP_DIR = Path(__file__).resolve().parents[2] / "app"


def test_keys_are_snake_case():
    bad = [k for k in ERRORS if not _SNAKE_CASE.match(k)]
    assert not bad, f"non snake_case error keys: {bad}"


def test_values_are_namespaced_i18n_keys():
    # Every value is an "api.<feature>.<key>" i18n key the frontend can translate.
    bad = [k for k, v in ERRORS.items() if not v.startswith("api.") or v.count(".") < 2]
    assert not bad, f"malformed i18n values for keys: {bad}"


def test_raised_keys_are_registered():
    # Static sweep over app/ — catches a typo'd key without exercising the code path.
    # (APIException also rejects unregistered keys at raise time.)
    unregistered = {
        f"{path.relative_to(_APP_DIR.parent)}: {key}"
        for path in _APP_DIR.rglob("*.py")
        for key in _RAISE_CALL.findall(path.read_text())
        if key not in ERRORS
    }
    assert not unregistered, f"raise_* called with keys missing from ERRORS: {sorted(unregistered)}"

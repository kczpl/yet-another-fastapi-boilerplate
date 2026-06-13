import re

from app.core.errors import ERRORS

_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")


def test_keys_are_snake_case():
    bad = [k for k in ERRORS if not _SNAKE_CASE.match(k)]
    assert not bad, f"non snake_case error keys: {bad}"


def test_values_are_namespaced_i18n_keys():
    # Every value is an "api.<feature>.<key>" i18n key the frontend can translate.
    bad = [k for k, v in ERRORS.items() if not v.startswith("api.") or v.count(".") < 2]
    assert not bad, f"malformed i18n values for keys: {bad}"

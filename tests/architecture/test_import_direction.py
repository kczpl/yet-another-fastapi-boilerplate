import ast

import pytest

from tests.architecture.source import APP_DIR, imported_modules, python_files

# The bottom layers import nothing from the layers above them. app/utils may import app/core.
UPPER_LAYERS = ("app.api", "app.features", "app.integrations", "app.main", "app.models", "app.services", "app.workers")
FORBIDDEN_IMPORTS = {
    "core": UPPER_LAYERS,
    "utils": UPPER_LAYERS,
}


def _upward_imports(source: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{node.lineno}: {module}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for module in imported_modules(node)
        if module.startswith(forbidden)
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from app.features.items.models import Item", ["1: app.features.items.models"]),
        ("def f():\n    import app.workers.enqueue", ["2: app.workers.enqueue"]),
        ("from app.core.config import api_config", []),
    ],
    ids=["module_level", "function_body", "same_layer"],
)
def test_finds_upward_imports(source: str, expected: list[str]):
    assert _upward_imports(source, UPPER_LAYERS) == expected


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_bottom_layer_never_imports_upward(layer: str):
    offenders = [
        f"{path.relative_to(APP_DIR)}:{found}"
        for path in python_files(APP_DIR / layer)
        for found in _upward_imports(path.read_text(), FORBIDDEN_IMPORTS[layer])
    ]
    assert offenders == []

import ast

import pytest

from tests.architecture.source import APP_DIR, imported_modules, python_files

ENQUEUE_MODULE = APP_DIR / "workers" / "enqueue.py"


def _publish_calls(source: str) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"delay", "apply_async"}
    ]


def _feature_imports(source: str) -> list[int]:
    # Only module-level imports: task bodies import services on purpose.
    return [
        node.lineno
        for node in ast.parse(source).body
        if any(module.startswith("app.features") for module in imported_modules(node))
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("summarize_item_task.delay(item_id)", [1]),
        ("task.apply_async((item_id,), {})", [1]),
        ("await enqueue_summarize_item(item_id)", []),
    ],
    ids=["delay", "apply_async", "helper"],
)
def test_finds_direct_publish_calls(source: str, expected: list[int]):
    assert _publish_calls(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from app.features.items.services.summarize import SummarizeItemService", [1]),
        ("def task():\n    from app.features.items.services.summarize import SummarizeItemService", []),
    ],
    ids=["module_level", "task_body"],
)
def test_finds_module_level_feature_imports(source: str, expected: list[int]):
    assert _feature_imports(source) == expected


def test_feature_code_publishes_only_through_enqueue_helpers():
    offenders = [
        f"{path.relative_to(APP_DIR)}:{line}"
        for path in python_files(APP_DIR)
        if path.relative_to(APP_DIR).parts[0] != "workers"
        for line in _publish_calls(path.read_text())
    ]
    assert offenders == [], "Await an enqueue_* helper of app/workers/enqueue.py instead."


def test_workers_import_no_features_at_module_level():
    # enqueue.py imports registry.py, and feature services import enqueue.py: an import cycle.
    offenders = [
        f"workers/{path.name}:{line}"
        for path in sorted((APP_DIR / "workers").glob("*.py"))
        for line in _feature_imports(path.read_text())
    ]
    assert offenders == []


def test_public_enqueue_helpers_are_async():
    # A sync helper publishes on the event loop thread.
    public = [
        node
        for node in ast.parse(ENQUEUE_MODULE.read_text()).body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_")
    ]
    offenders = [node.name for node in public if not isinstance(node, ast.AsyncFunctionDef)]
    misnamed = [node.name for node in public if not node.name.startswith("enqueue_")]
    assert public
    assert offenders == []
    assert misnamed == []

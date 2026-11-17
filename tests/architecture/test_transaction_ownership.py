import ast

import pytest

from tests.architecture.source import APP_DIR


def _repository_files() -> list:
    features = APP_DIR / "features"
    return sorted([*features.glob("*/repository.py"), *features.glob("*/repository/*.py")])


def _ownership_violations(source: str) -> list[str]:
    # The caller owns the transaction. A repository flushes and never commits.
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "commit":
            found.append(f"{node.lineno}: commit()")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            found.extend(f"{node.lineno}: {node.name}(commit=...)" for arg in arguments if arg.arg == "commit")
    return found


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("async def save(db):\n    await db.commit()", ["2: commit()"]),
        ("async def save(db, *, commit=True):\n    await db.flush()", ["1: save(commit=...)"]),
        ("async def save(db):\n    await db.flush()", []),
    ],
    ids=["commit_call", "commit_parameter", "flush_only"],
)
def test_finds_commits_and_commit_parameters(source: str, expected: list[str]):
    assert _ownership_violations(source) == expected


def test_repositories_never_commit():
    files = _repository_files()
    offenders = [
        f"{path.relative_to(APP_DIR)}:{violation}"
        for path in files
        for violation in _ownership_violations(path.read_text())
    ]
    assert files
    assert offenders == [], "Repositories flush only. The service or session_scope() commits."

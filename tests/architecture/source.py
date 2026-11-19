import ast
from collections.abc import Iterator
from pathlib import Path

# Shared helpers of the architecture tests. They read the source and import nothing from app/.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"


def python_files(root: Path) -> Iterator[Path]:
    yield from sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def imported_modules(node: ast.AST) -> list[str]:
    # Each imported name counts too, so `from app import features` gives app.features.
    # Ruff TID252 bans relative imports.
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
    return []

import ast
from collections.abc import Iterator
from pathlib import Path

# Shared helpers of the architecture tests. They read the source and import nothing from app/.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"


def python_files(root: Path) -> Iterator[Path]:
    yield from sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def imported_modules(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0:
        return [node.module or ""]
    return []

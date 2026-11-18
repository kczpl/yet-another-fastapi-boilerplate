import importlib.util
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_guidance():
    # .agents/ is not a package. Load the script from its path.
    spec = importlib.util.spec_from_file_location("agent_guidance", PROJECT_ROOT / ".agents" / "guidance.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guidance = _load_guidance()

BASE = {
    "AGENTS.md": "Read `.agents/rules/core.md`. Run `just ci`.\n",
    "justfile": "set dotenv-load\n\nci:\n  echo ok\n",
    ".agents/rules/core.md": "# Core\n",
    ".agents/rules/backend/db.md": '---\npaths:\n  - "app/**/*.py"\n---\n\n# Database\n',
    "app/main.py": "",
}


def _repository(root: Path, files: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True)  # noqa: S603, S607 — fixed git command, temporary directory
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    return root


def test_consistent_guidance_has_no_problems(tmp_path: Path):
    assert guidance.check(_repository(tmp_path, BASE)) == []


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"CLAUDE.md": "# Claude\n"}, "CLAUDE.md: tool adapter; keep agent guidance in AGENTS.md and .agents/"),
        (
            {".agents/rules/extra.md": "# Extra\n"},
            ".agents/rules/extra.md: a global rule has no paths: and AGENTS.md names it",
        ),
        (
            {".agents/rules/backend/api.md": "# API\n"},
            ".agents/rules/backend/api.md: a scoped rule needs a paths: list",
        ),
        (
            {".agents/rules/backend/api.md": '---\npaths:\n  - "app/api/**"\n---\n'},
            ".agents/rules/backend/api.md: 'app/api/**': app/api does not exist",
        ),
        (
            {".agents/rules/core.md": "line\n" * 101},
            ".agents/rules/core.md: more than 100 lines; move details to .agents/references/",
        ),
        ({"README.md": "[Guide](docs/missing.md)\n"}, "README.md: broken link docs/missing.md"),
        ({"README.md": "See `app/missing.py:3`.\n"}, "README.md: missing path `app/missing.py:3`"),
        ({"README.md": "```bash\njust deploy   # ship it\n```\n"}, "README.md: unknown recipe `just deploy`"),
    ],
    ids=["adapter", "unnamed_global", "scoped_without_paths", "stale_pattern", "long_rule", "link", "path", "recipe"],
)
def test_reports_each_problem(tmp_path: Path, change: dict[str, str], problem: str):
    assert guidance.check(_repository(tmp_path, {**BASE, **change})) == [problem]


def test_glob_for_future_files_needs_only_its_directory(tmp_path: Path):
    # A new project has no feature yet; the rule still names where the features go.
    rule = '---\npaths:\n  - "app/features/*/models.py"\n---\n'
    files = {**BASE, ".agents/rules/backend/db.md": rule, "app/features/__init__.py": ""}

    assert guidance.check(_repository(tmp_path, files)) == []


def test_routes_a_file_to_the_rules_whose_paths_match():
    rules = {".agents/rules/backend/db.md": ["app/**/*.py"], ".agents/rules/backend/testing.md": ["tests/**"]}

    assert guidance.matching_rules(rules, ["app/features/items/models.py"]) == [".agents/rules/backend/db.md"]


def test_repository_guidance_is_consistent():
    # The same check as `just agents-check`, so `just ci` covers it.
    assert guidance.check(PROJECT_ROOT) == []

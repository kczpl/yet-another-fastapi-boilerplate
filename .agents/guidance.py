import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

# Routes and checks the agent guidance. Run it through just: `just rules <files>` and
# `just agents-check`. It needs Python 3.13+ (PurePosixPath.full_match) and no packages.
ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = ".agents/rules"
MAX_RULE_LINES = 100
FORBIDDEN_FILES = ("CLAUDE.md", "CLAUDE.local.md")
FORBIDDEN_DIRS = (".claude/", ".codex/")
PATH_ROOTS = (".agents/", ".github/", "alembic/", "app/", "docs/", "scripts/", "tests/")
PLACEHOLDER = re.compile(r"[*<>{}\s]|\.\.\.")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
RECIPE = re.compile(r"^(?:alias\s+)?([A-Za-z_][\w-]*)")
RECIPE_NAME = re.compile(r"[a-z][\w-]*")


def rule_paths(text: str) -> list[str] | None:
    # None means a global rule: it has no frontmatter.
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    paths = []
    for line in lines[1 : lines.index("---", 1)]:
        item = line.strip()
        if item.startswith("- "):
            paths.append(item[2:].strip().strip("\"'"))
    return paths


def repository_files(root: Path) -> list[str]:
    command = ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"]
    listed = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603 — fixed git command
    return sorted(path for path in listed.stdout.splitlines() if (root / path).exists())


def scoped_rules(root: Path, files: list[str]) -> dict[str, list[str]]:
    return {
        path: rule_paths((root / path).read_text()) or []
        for path in files
        if path.startswith(f"{RULES_DIR}/") and path.count("/") > 2 and path.endswith(".md")
    }


def matching_rules(rules: dict[str, list[str]], targets: list[str]) -> list[str]:
    return sorted(
        rule
        for rule, patterns in rules.items()
        if any(PurePosixPath(target).full_match(pattern) for target in targets for pattern in patterns)
    )


def normalize(target: str, root: Path) -> str:
    path = Path(target)
    if path.is_absolute():
        return path.resolve().relative_to(root.resolve()).as_posix()
    return PurePosixPath(target.removeprefix("./")).as_posix()


################################################################################
# checks #
################################################################################


def check_layout(files: list[str]) -> list[str]:
    return [
        f"{path}: tool adapter; keep agent guidance in AGENTS.md and .agents/"
        for path in files
        if PurePosixPath(path).name in FORBIDDEN_FILES or path.startswith(FORBIDDEN_DIRS)
    ]


def check_rules(root: Path, files: list[str]) -> list[str]:
    agents = (root / "AGENTS.md").read_text()
    rules = [path for path in files if path.startswith(f"{RULES_DIR}/") and path.endswith(".md")]
    return [problem for path in rules for problem in _rule_problems(root, files, path, agents)]


def _rule_problems(root: Path, files: list[str], path: str, agents: str) -> list[str]:
    text = (root / path).read_text()
    patterns = rule_paths(text)
    problems = []
    if path.count("/") == 2:
        if patterns is not None or path not in agents:
            problems.append(f"{path}: a global rule has no paths: and AGENTS.md names it")
    elif not patterns:
        problems.append(f"{path}: a scoped rule needs a paths: list")
    problems.extend(
        f"{path}: {pattern!r} matches no file" for pattern in patterns or [] if not _matches(files, pattern)
    )
    if len(text.splitlines()) > MAX_RULE_LINES:
        problems.append(f"{path}: more than {MAX_RULE_LINES} lines; move details to .agents/references/")
    return problems


def _matches(files: list[str], pattern: str) -> bool:
    return any(PurePosixPath(path).full_match(pattern) for path in files)


def check_links(root: Path, files: list[str]) -> list[str]:
    problems = []
    for path in _markdown(files):
        for target in LINK.findall((root / path).read_text()):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            if not (root / path).parent.joinpath(target.split("#")[0]).exists():
                problems.append(f"{path}: broken link {target}")
    return problems


def check_references(root: Path, files: list[str]) -> list[str]:
    recipes = just_recipes(root)
    problems = []
    for path in _instructions(files):
        for span in _code_references(root / path):
            problems.extend(f"{path}: {problem}" for problem in _span_problems(root, span, recipes))
    return problems


def _span_problems(root: Path, span: str, recipes: set[str]) -> list[str]:
    words = span.split()
    if words[:1] == ["just"]:
        name = words[1] if len(words) > 1 else ""
        unknown = RECIPE_NAME.fullmatch(name) is not None and name not in recipes
        return [f"unknown recipe `{span}`"] if unknown else []
    if not span.startswith(PATH_ROOTS) or PLACEHOLDER.search(span):
        return []
    path = re.split(r":\d|::", span)[0]
    return [] if (root / path).exists() else [f"missing path `{span}`"]


def _code_references(path: Path) -> list[str]:
    # Inline code spans and the `just ...` lines of fenced blocks.
    text = path.read_text()
    fenced = [line.strip() for line in text.splitlines() if line.strip().startswith("just ")]
    return [*CODE_SPAN.findall(text), *(line.split("#")[0].strip() for line in fenced)]


def just_recipes(root: Path) -> set[str]:
    names = set()
    for line in (root / "justfile").read_text().splitlines():
        match = RECIPE.match(line)
        if match and not line.startswith(("set ", "export ")) and ":" in line:
            names.add(match.group(1))
    return names


def _markdown(files: list[str]) -> list[str]:
    return [path for path in files if path.endswith(".md") and not path.startswith(".agents/archive/")]


def _instructions(files: list[str]) -> list[str]:
    return [path for path in _markdown(files) if path in ("AGENTS.md", "README.md") or path.startswith(".agents/")]


def check(root: Path) -> list[str]:
    files = repository_files(root)
    return [
        *check_layout(files),
        *check_rules(root, files),
        *check_links(root, files),
        *check_references(root, files),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Route and check the agent guidance.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--paths", nargs="+", help="files you will change; prints the scoped rules to read")
    group.add_argument("--index", action="store_true", help="print each scoped rule and its paths")
    group.add_argument("--check", action="store_true", help="check the rules, links, paths and recipes")
    args = parser.parse_args()
    rules = scoped_rules(ROOT, repository_files(ROOT))
    if args.check:
        problems = check(ROOT)
        sys.stdout.write("".join(f"{problem}\n" for problem in problems) or "Agent guidance is consistent.\n")
        return 1 if problems else 0
    if args.index:
        sys.stdout.write("".join(f"{rule}: {', '.join(patterns)}\n" for rule, patterns in sorted(rules.items())))
        return 0
    targets = [normalize(target, ROOT) for target in args.paths]
    sys.stdout.write("".join(f"{rule}\n" for rule in matching_rules(rules, targets)) or "No scoped rule.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

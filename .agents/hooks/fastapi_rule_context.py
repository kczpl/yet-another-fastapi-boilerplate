#!/usr/bin/env python3
"""Select Python rules by path, or provide shared context as a coding-tool hook."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTING_REMINDER = (
    "Before editing, run python3 .agents/hooks/fastapi_rule_context.py --paths <file> ... "
    "from the repository root and read the listed rules. Use individual intended files, including tests."
)
PATCH_PATHS = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.MULTILINE)


def glob_regex(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern)
    return re.compile(
        "^"
        + escaped.replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        + "$"
    )


@dataclass(frozen=True)
class Rule:
    path: str
    globs: tuple[str, ...]

    def matches(self, path: str) -> bool:
        return any(glob_regex(pattern).fullmatch(path) for pattern in self.globs)


def load_rules(root: Path) -> list[Rule]:
    rules = []
    for path in sorted((root / ".agents/rules").rglob("*.md")):
        header, separator, _ = path.read_text(encoding="utf-8").partition("\n---\n")
        lines = header.splitlines()
        if not separator or lines[:2] != ["---", "paths:"]:
            raise ValueError(f"{path}: expected paths: frontmatter")
        globs = tuple(parse_glob(line, path) for line in lines[2:])
        if not globs:
            raise ValueError(f"{path}: paths: must not be empty")
        rules.append(Rule(path.relative_to(root).as_posix(), globs))
    if not rules:
        raise ValueError("No rules found in .agents/rules")
    return rules


def parse_glob(line: str, path: Path) -> str:
    match = re.fullmatch(r'  - "([^"\s]+)"', line)
    if match is None:
        raise ValueError(f"{path}: use a double-quoted glob on each paths: line")
    pattern = match[1]
    if pattern.startswith("/") or ".." in pattern.split("/") or any(char in pattern for char in "[]{}\\"):
        raise ValueError(f"{path}: unsupported glob {pattern!r}; use relative paths with *, ** or ?")
    return pattern


def select_rules(root: Path, cwd: Path, paths: list[str]) -> list[Rule]:
    relative = []
    for name in paths:
        path = (cwd / name).resolve()
        if not path.is_relative_to(root):
            continue
        if path.is_dir():
            raise ValueError(f"{name}: pass individual files, or use --index")
        relative.append(path.relative_to(root).as_posix())
    return [rule for rule in load_rules(root) if any(rule.matches(path) for path in relative)]


def session_state(root: Path, payload: dict) -> Path | None:
    session = payload.get("session_id")
    if not session:
        return None
    key = f"{root}\0{session}\0{payload.get('agent_id') or ''}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache / "fastapi-agent-context" / digest


def announce_once(state: Path | None, name: str) -> bool:
    if state is None:
        return True
    state.mkdir(parents=True, exist_ok=True)
    marker = state / hashlib.sha256(name.encode()).hexdigest()
    try:
        marker.touch(mode=0o600, exist_ok=False)
    except FileExistsError:
        return False
    return True


def render_routes(rules: list[Rule], state: Path | None = None) -> str:
    paths = [rule.path for rule in rules if announce_once(state, rule.path)]
    if not paths:
        return ""
    return "Read these rules now unless already in context (listed once per session):\n" + "\n".join(
        f"- {path}" for path in paths
    )


def tool_context(root: Path, payload: dict, state: Path | None) -> str:
    tool = payload.get("tool_name")
    if tool == "Bash":
        return ROUTING_REMINDER if announce_once(state, "shell-reminder") else ""
    data = payload.get("tool_input") or {}
    if not isinstance(data, dict):
        raise ValueError("tool_input must be an object")
    if tool == "apply_patch":
        paths = PATCH_PATHS.findall(data.get("command", ""))
    elif tool in {"Read", "Edit", "Write"}:
        paths = [data["file_path"]] if data.get("file_path") else []
    else:
        return ""
    cwd = Path(data.get("workdir") or payload.get("cwd") or root).resolve()
    return render_routes(select_rules(root, cwd, paths), state)


def process(root: Path, payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    state = session_state(root, payload)
    if event in {"SessionStart", "SubagentStart"}:
        if state is not None:
            shutil.rmtree(state, ignore_errors=True)
        context = "Project instructions (skip a duplicate read if already in context):\n\n" + (
            root / "AGENTS.md"
        ).read_text(encoding="utf-8")
    elif event == "PreToolUse":
        context = tool_context(root, payload, state)
    else:
        return None
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}} if context else None


def check(root: Path) -> None:
    rules = load_rules(root)
    if len((root / "AGENTS.md").read_bytes()) > 8000:
        raise ValueError("AGENTS.md exceeds the 8000-byte startup budget")
    if len(render_routes(rules).encode()) > 2048:
        raise ValueError("Rule listing exceeds the 2048-byte hook budget")
    if (root / "CLAUDE.md").exists() or (root / ".claude/rules").exists():
        raise ValueError("Keep project guidance in AGENTS.md and .agents/rules")
    print(f"Agent guidance OK: {len(rules)} scoped rules; hook context within budget.")


def run_hook() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("Hook input must be a JSON object")
    if output := process(ROOT, payload):
        print(json.dumps(output))


def run_cli(args: argparse.Namespace) -> None:
    if args.paths:
        for rule in select_rules(ROOT, Path.cwd(), args.paths):
            print(rule.path)
    elif args.index:
        for rule in load_rules(ROOT):
            print(f"{rule.path}: {', '.join(rule.globs)}")
    elif args.check:
        check(ROOT)
    else:
        run_hook()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--paths", nargs="+", metavar="FILE")
    mode.add_argument("--index", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        run_cli(args)
    except (OSError, ValueError, TypeError) as error:
        print(f"Agent context: {error}", file=sys.stderr)
        return 1 if args.paths or args.index or args.check else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

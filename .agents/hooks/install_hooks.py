#!/usr/bin/env python3
"""Merge shared hooks into user settings, preserving other hooks and backing up changes."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).with_name("hooks.json")


def validate_groups(groups: object, path: Path) -> None:
    if not isinstance(groups, list):
        raise ValueError(f"{path}: hook events must be lists")
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            raise ValueError(f"{path}: invalid hook group")
        if any(not isinstance(handler, dict) for handler in group["hooks"]):
            raise ValueError(f"{path}: invalid hook handler")


def read_settings(path: Path) -> dict:
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
        raise ValueError(f"{path}: expected a JSON object with a hooks object")
    for groups in settings.get("hooks", {}).values():
        validate_groups(groups, path)
    return settings


def configured_template(common_dir: str, tool: str) -> tuple[dict, str]:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    identity = f'[ "$c" = {shlex.quote(common_dir)} ]'
    for groups in template["hooks"].values():
        for group in groups:
            for handler in group["hooks"]:
                handler["command"] = handler["command"].replace("__REPO_COMMON_DIR__", shlex.quote(common_dir))
                if tool == "Claude Code":
                    handler.pop("additionalContextLimit", None)
    return template, identity


def owns(handler: dict, identity: str) -> bool:
    command = handler.get("command", "")
    return isinstance(command, str) and identity in command and ".agents/hooks/fastapi_rule_context.py" in command


def without_ours(groups: list[dict], identity: str) -> list[dict]:
    kept = []
    for group in groups:
        handlers = [handler for handler in group["hooks"] if not owns(handler, identity)]
        if handlers or not group["hooks"]:
            kept.append({**group, "hooks": handlers})
    return kept


def merge(settings: dict, template: dict, identity: str) -> dict:
    merged = copy.deepcopy(settings)
    hooks = merged.setdefault("hooks", {})
    for event, groups in list(hooks.items()):
        kept = without_ours(groups, identity)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    for event, groups in template["hooks"].items():
        hooks.setdefault(event, []).extend(copy.deepcopy(groups))
    return merged


def write_settings(path: Path, settings: dict) -> None:
    if path.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{stamp}"))
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        if path.exists():
            shutil.copymode(path, temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install(home: Path, common_dir: str, check: bool = False, codex_home: Path | None = None) -> int:
    targets = {"Claude Code": home / ".claude/settings.json", "Codex": (codex_home or home / ".codex") / "hooks.json"}
    pending = []
    # Read both files before changing either, so malformed settings leave both untouched.
    for tool, target in targets.items():
        if not target.parent.is_dir():
            print(f"{tool}: skipped ({target.parent} does not exist)")
            continue
        path = target.resolve()  # Preserve a dotfiles symlink by writing its target.
        settings = read_settings(path)
        template, identity = configured_template(common_dir, tool)
        pending.append((tool, path, settings, merge(settings, template, identity)))
    outdated = False
    for tool, path, settings, merged in pending:
        if merged == settings:
            print(f"{tool}: up to date")
        elif check:
            outdated = True
            print(f"{tool}: missing or outdated hooks; run just agents-install")
        else:
            write_settings(path, merged)
            print(f"{tool}: installed in {path}")
    return int(outdated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without changing files")
    parser.add_argument("--home", type=Path, help="use another home directory (for isolated testing)")
    args = parser.parse_args()
    try:
        git = shutil.which("git")
        if git is None:
            raise OSError("Git is required to install hooks")
        common_dir = subprocess.check_output(  # noqa: S603 -- Resolved Git executable with fixed arguments.
            [git, "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, text=True
        ).strip()
        codex_home = Path(os.environ["CODEX_HOME"]) if not args.home and os.environ.get("CODEX_HOME") else None
        result = install(args.home or Path.home(), common_dir, args.check, codex_home)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Hook installation: {error}", file=sys.stderr)
        return 1
    if not args.check:
        print("Start a fresh session. In Codex, open /hooks to review and trust the new handlers.")
    return result


if __name__ == "__main__":
    sys.exit(main())

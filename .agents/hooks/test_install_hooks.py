"""Exercise installation against isolated settings, never the developer's home."""

import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import install_hooks as installer


class InstallHooksTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        self.common_dir = str(self.home / "repo with spaces/.git")
        self.template, self.identity = installer.configured_template(self.common_dir, "Codex")
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_merge_preserves_settings_mixed_groups_and_other_repositories(self):
        ours = self.template["hooks"]["PreToolUse"][0]["hooks"][0]
        other, _ = installer.configured_template("/another/repository/.git", "Codex")
        foreign = other["hooks"]["PreToolUse"][0]["hooks"][0]
        custom = {"type": "command", "command": "custom-hook"}
        settings = {
            "permissions": {"allow": ["Bash(uv run ruff:*)"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [ours, custom, foreign]}]},
        }
        merged = installer.merge(settings, self.template, self.identity)
        self.assertEqual(merged["permissions"], settings["permissions"])
        self.assertEqual(merged["hooks"]["PreToolUse"][0]["hooks"], [custom, foreign])
        self.assertEqual(installer.merge(merged, self.template, self.identity), merged)
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["hooks"], [ours, custom, foreign])

    def test_install_backs_up_once_and_is_idempotent(self):
        path = self.home / ".claude/settings.json"
        original = '{"permissions": {"allow": []}}\n'
        path.write_text(original)
        self.assertEqual(installer.install(self.home, self.common_dir, check=True), 1)
        self.assertEqual(path.read_text(), original)
        self.assertEqual(installer.install(self.home, self.common_dir), 0)
        backups = list(path.parent.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        before = path.stat().st_mtime_ns
        self.assertEqual(installer.install(self.home, self.common_dir), 0)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(installer.install(self.home, self.common_dir, check=True), 0)
        self.assertEqual(list(path.parent.glob("settings.json.bak-*")), backups)

    def test_malformed_settings_leave_both_targets_untouched(self):
        claude = self.home / ".claude/settings.json"
        codex = self.home / ".codex/hooks.json"
        claude.write_text("{}\n")
        for text in ["invalid JSON", "[]", '{"hooks": {"PreToolUse": {}}}']:
            with self.subTest(text=text):
                codex.write_text(text)
                with self.assertRaises(ValueError):
                    installer.install(self.home, self.common_dir)
                self.assertEqual(claude.read_text(), "{}\n")
                self.assertEqual(codex.read_text(), text)
        self.assertEqual(list(claude.parent.glob("*.bak-*")), [])

    def test_symlink_is_preserved_and_target_is_backed_up(self):
        target = self.home / "dotfile.json"
        target.write_text("{}\n")
        path = self.home / ".claude/settings.json"
        path.symlink_to(target)
        installer.install(self.home, self.common_dir)
        self.assertTrue(path.is_symlink())
        self.assertIn("hooks", json.loads(target.read_text()))
        self.assertEqual(len(list(self.home.glob("dotfile.json.bak-*"))), 1)

    def test_tool_specific_fields_and_custom_codex_home(self):
        claude, _ = installer.configured_template(self.common_dir, "Claude Code")
        self.assertNotIn("additionalContextLimit", claude["hooks"]["SessionStart"][0]["hooks"][0])
        custom = self.home / "custom-codex"
        custom.mkdir()
        installer.install(self.home, self.common_dir, codex_home=custom)
        self.assertTrue((custom / "hooks.json").exists())
        self.assertFalse((self.home / ".codex/hooks.json").exists())

    def test_command_runs_from_subdirectory_and_worktree_but_skips_foreign_repository(self):
        git = shutil.which("git")
        shell = shutil.which("sh")
        if git is None or shell is None:
            self.skipTest("Git and a POSIX shell are required")
        repo = self.home / "repo with spaces"
        repo.mkdir()

        def git_command(*args):
            return subprocess.check_output(
                [git, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
                cwd=repo,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

        git_command("init")
        hook = repo / ".agents/hooks/fastapi_rule_context.py"
        hook.parent.mkdir(parents=True)
        hook.write_text('print("hook executed")\n')
        git_command("add", ".agents")
        git_command("-c", "user.name=Hook Test", "-c", "user.email=hooks@example.test", "commit", "-m", "fixture")
        common_dir = git_command("rev-parse", "--path-format=absolute", "--git-common-dir")
        template, _ = installer.configured_template(common_dir, "Codex")
        command = template["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        worktree = self.home / "linked worktree"
        git_command("worktree", "add", "--detach", str(worktree))
        for cwd in [hook.parent, worktree]:
            output = subprocess.check_output([shell, "-c", command], cwd=cwd, text=True)
            self.assertEqual(output.strip(), "hook executed")
        foreign = self.home / "foreign"
        foreign.mkdir()
        subprocess.check_call([git, "init", str(foreign)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        foreign_hook = foreign / ".agents/hooks/fastapi_rule_context.py"
        foreign_hook.parent.mkdir(parents=True)
        foreign_hook.write_text('raise RuntimeError("Foreign hook must not execute")\n')
        self.assertEqual(subprocess.check_output([shell, "-c", command], cwd=foreign, text=True), "")


if __name__ == "__main__":
    unittest.main()

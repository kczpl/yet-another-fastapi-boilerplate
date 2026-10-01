"""Check rule selection and the context actually delivered by lifecycle hooks."""

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import fastapi_rule_context as context


class RuleContextTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        cache = patch.dict(os.environ, {"XDG_CACHE_HOME": self.temporary.name})
        cache.start()
        self.addCleanup(cache.stop)

    def payload(self, event="PreToolUse", tool="Edit", agent=""):
        return {
            "hook_event_name": event,
            "session_id": "test-session",
            "agent_id": agent,
            "cwd": str(context.ROOT),
            "tool_name": tool,
            "tool_input": {"file_path": "app/features/items/routes.py"},
        }

    def test_scopes_match_direct_nested_and_new_files(self):
        for path in ["app/main.py", "app/new/nested/module.py"]:
            with self.subTest(path=path):
                rules = context.select_rules(context.ROOT, context.ROOT, [path])
                self.assertEqual({Path(rule.path).stem for rule in rules}, {"core", "database"})
        rules = context.select_rules(context.ROOT, context.ROOT, ["tests/new/test_example.py"])
        self.assertEqual([Path(rule.path).stem for rule in rules], ["testing"])

    def test_relative_absolute_and_outside_paths(self):
        cwd = context.ROOT / "app/features/items"
        relative = context.select_rules(context.ROOT, cwd, ["routes.py"])
        absolute = context.select_rules(context.ROOT, cwd, [str(cwd / "routes.py")])
        self.assertEqual(relative, absolute)
        self.assertIn("routes", {Path(rule.path).stem for rule in relative})
        self.assertEqual(context.select_rules(context.ROOT, cwd, [self.temporary.name + "/outside.py"]), [])
        with self.assertRaisesRegex(ValueError, "individual files"):
            context.select_rules(context.ROOT, context.ROOT, ["app"])

    def test_patch_move_selects_both_scopes_without_reading_patch_body(self):
        payload = self.payload(tool="apply_patch")
        payload["tool_input"] = {
            "command": "*** Update File: app/features/items/routes.py\n"
            "*** Move to: tests/features/items/test_new.py\n@@\n+secret text must not appear\n"
        }
        result = context.process(context.ROOT, payload)
        text = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("backend/routes.md", text)
        self.assertIn("backend/testing.md", text)
        self.assertNotIn("secret text", text)

    def test_rules_once_per_session_with_separate_subagent_and_compaction_reset(self):
        payload = self.payload()
        self.assertIsNotNone(context.process(context.ROOT, payload))
        self.assertIsNone(context.process(context.ROOT, payload))
        self.assertIsNotNone(context.process(context.ROOT, self.payload(agent="child")))
        startup = self.payload(event="SessionStart")
        startup["source"] = "compact"
        result = context.process(context.ROOT, startup)
        self.assertIn("# Agent instructions", result["hookSpecificOutput"]["additionalContext"])
        self.assertIsNotNone(context.process(context.ROOT, payload))
        self.assertIsNone(context.process(context.ROOT, self.payload(agent="child")))

    def test_stateless_payloads_repeat_guidance(self):
        payload = self.payload()
        del payload["session_id"]
        self.assertEqual(context.process(context.ROOT, payload), context.process(context.ROOT, payload))

    def test_shell_reminder_never_exposes_or_executes_command(self):
        sentinel = Path(self.temporary.name) / "sentinel"
        payload = self.payload(tool="Bash")
        payload["tool_input"] = {"command": f"touch {sentinel}; echo private-command"}
        output = context.process(context.ROOT, payload)
        self.assertEqual(output["hookSpecificOutput"]["additionalContext"], context.ROUTING_REMINDER)
        self.assertFalse(sentinel.exists())
        self.assertIsNone(context.process(context.ROOT, payload))

    def test_parallel_hooks_announce_each_rule_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: context.process(context.ROOT, self.payload()), range(8)))
        text = "\n".join(result["hookSpecificOutput"]["additionalContext"] for result in results if result)
        self.assertEqual(text.count("backend/routes.md"), 1)
        self.assertEqual(text.count("backend/core.md"), 1)

    def test_invalid_frontmatter_reports_the_rule(self):
        root = Path(self.temporary.name)
        rules = root / ".agents/rules"
        rules.mkdir(parents=True)
        path = rules / "bad.md"
        path.write_text("---\npaths: []\n---\nBad rule\n")
        with self.assertRaisesRegex(ValueError, "bad.md"):
            context.load_rules(root)


if __name__ == "__main__":
    unittest.main()

# Shared agent guidance

This template keeps one small instruction tree:

```text
AGENTS.md                    # Project conventions and development commands
.agents/
├── rules/backend/           # Existing Python rules with paths: frontmatter
└── hooks/
    ├── hooks.json           # Shared hook template
    ├── fastapi_rule_context.py
    ├── install_hooks.py
    └── test_*.py
```

Codex reads `AGENTS.md` directly. With the hooks installed, Claude Code receives
the same instructions at startup. No project-specific tool adapters are needed.
Tools without hooks follow the routing command in `AGENTS.md`.

## Read the relevant rules

From the repository root:

```bash
python3 .agents/hooks/fastapi_rule_context.py --paths app/features/items/routes.py tests/features/items/test_routes.py
python3 .agents/hooks/fastapi_rule_context.py --index
```

Paths resolve from the current working directory and may name files that do not
exist yet. Pass individual files, not directories. From a subdirectory, use the
script's absolute path. The router prints rule paths; read those rules before editing.

Each rule starts with a `paths:` block list of double-quoted globs. Supported
wildcards are `*`, `**` and `?`; `**/` also matches zero directories. Keep scope
only in this frontmatter. Add rules when the template gains an actual convention.

## Install hooks

Requirements: macOS/Linux, Python 3.11+, Git, and a tool version supporting these hook events.

```bash
just agents-install
python3 .agents/hooks/install_hooks.py --check
```

The installer merges the template into `~/.claude/settings.json` and
`${CODEX_HOME:-~/.codex}/hooks.json`, skipping tools whose directories do not
exist. It preserves unrelated settings and hooks, backs up changed files, and is
safe to run again. It binds handlers to this repository's Git common directory,
so they also work in linked worktrees and do nothing in other repositories.
Install again for a separate clone. `--check` changes no files.

In Codex, open `/hooks` to review and trust the new handlers, then start a fresh
session. See the [official OpenAI hook documentation](https://learn.chatgpt.com/docs/hooks).
Neither tool reads hooks from `.agents/` automatically; installation is required.

| Event | Behavior |
|---|---|
| SessionStart: startup, clear, compact | Loads `AGENTS.md` and resets rule announcements. |
| SubagentStart | Loads the same instructions in the new context. |
| PreToolUse: Read, Edit, Write, apply_patch | Lists matching rules once per session/context. |
| PreToolUse: Bash | Reminds the agent once to route the intended files manually. |

Shell commands are never parsed or executed by the router. Patch headers include
added, changed, deleted and moved files. Hooks provide guidance; they do not prove
that a rule was read. Before editing, the manual routing step remains required.
After compaction, reload the rules needed for the next edit.

Announcement markers live under `${XDG_CACHE_HOME:-~/.cache}/fastapi-agent-context/`.
They are separate for each checkout, session and subagent. With no session ID,
hooks are stateless. The cache can be removed at any time.

## Verify changes

```bash
just agents-check
```

This validates rule scopes and context size and runs standard-library tests for
routing, hook output, session resets and safe installation. It needs no app
dependencies, database or paid model calls. Run it manually; it is not part of CI.
Python hook files also run through `just lint` and `just complexity`.

# Shared agent guidance

Edit agent instructions here, once. Root `AGENTS.md` is the entry point for every coding tool.
The repository has no tool adapters: no `CLAUDE.md`, `.claude/` or `.codex/`. Git ignores the
local `.claude/` and `.codex/` directories, so personal settings stay outside the repository.

| Path | Purpose |
|---|---|
| `rules/*.md` | Global rules. Every agent reads them at session start. |
| `rules/backend/*.md` | Scoped rules. The table in root `AGENTS.md` maps each area to its rules. |

## Tool support

- **Codex** and **Cursor** read `AGENTS.md`.
- **Claude Code** loads `AGENTS.md` through its built-in `agents-md` plugin. The plugin stands
  down when a project `CLAUDE.md` or `CLAUDE.local.md` exists, so do not add one.

No tool loads the rules automatically. `AGENTS.md` tells the agent which rules to read and when.

## Maintain the guidance

1. Put a rule for every task directly in `rules/` and name it in step 1 of `AGENTS.md`.
2. Put a rule for one area in `rules/backend/` and add it to the area table in `AGENTS.md`.
3. Keep each rule short. Write only what the code and the checks cannot show.
4. Use ASD-STE100 Simplified Technical English (see `rules/core.md`).
5. When code moves, update the paths in the rules and in the `AGENTS.md` table.
6. Start a new agent session to check a change. A listed file is no proof that the agent read it.

Upstream contracts: [AGENTS.md](https://agents.md/),
[Claude Code memory](https://code.claude.com/docs/en/memory).

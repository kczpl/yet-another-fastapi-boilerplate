# Shared agent guidance

Edit agent instructions here, once. Root `AGENTS.md` is the entry point for every coding tool.
The repository has no tool adapters: no `CLAUDE.md`, `.claude/` or `.codex/`. Git ignores the
local `.claude/` and `.codex/` directories, so personal settings stay outside the repository.

| Path | Purpose |
|---|---|
| `rules/*.md` | Global rules without `paths:`. Every agent reads them at session start. |
| `rules/backend/*.md` | Scoped rules. Their `paths:` frontmatter selects them for a file. |
| `references/*.md` | Details and procedures. An agent reads them when the task needs them. |
| `guidance.py` | The router (`just rules`) and the check (`just agents-check`). |
| `plans/` | Active plans of multi-step work. Create on demand. |
| `archive/plans/` | Plans that shipped. History only, not guidance. The check skips it. |
| `temp/` | Ignored scratch data and reports. Create on demand. |

## Tool support

- **Codex** and **Cursor** read `AGENTS.md`.
- **Claude Code** loads `AGENTS.md` through its built-in `agents-md` plugin. The plugin stands
  down when a project `CLAUDE.md` or `CLAUDE.local.md` exists, so do not add one.

No tool reads `paths:` from `.agents/`. `AGENTS.md` tells the agent to run `just rules` with
the files it will change and to read the listed rules. A large repository can add session
hooks that print the rules; this template keeps the manual step.

## Maintain the guidance

1. Put a rule for every task directly in `rules/` and name it in step 1 of `AGENTS.md`.
2. Put a rule for one area in a subdirectory of `rules/` with a `paths:` list of globs. Run
   `just rules <file>` with a matching file and see the rule in the output.
3. Keep each rule short: at most 100 lines. Write only what the code and the checks cannot
   show. Move details, procedures and examples to `references/` and link them from the rule.
4. Use ASD-STE100 Simplified Technical English (see `rules/core.md`).
5. Run `just agents-check` before a commit. It finds tool adapters, global rules that
   `AGENTS.md` does not name, scoped rules without `paths:`, globs that match no file, rules
   above the size limit, broken links, missing repository paths and unknown `just` recipes.
6. Start a new agent session to check a change. A listed file is no proof that the agent read it.

## Plans

Write a plan to `plans/<topic>.md` when work takes more than one session or more than one PR.
Give each step its check. Move the plan to `archive/plans/` when the work ships.

Upstream contracts: [AGENTS.md](https://agents.md/),
[Claude Code memory](https://code.claude.com/docs/en/memory).

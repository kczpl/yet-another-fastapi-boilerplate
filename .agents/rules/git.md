# Git workflow

## Branches and PRs

- `master` is the default branch. Keep it releasable.
- Do work on a short-lived branch from the current `master`: `feat/<desc>`, `fix/<desc>` or
  `chore/<desc>`. Do not rename the current branch unless the user asks.
- Before a PR, run `just ci` and confirm documentation readiness (`core.md` §5 and §8).
- Open the PR with `--base master`. Merge with **Squash and merge**: one PR is one commit.
- Never force-push `master`. Never rewrite history that others use.
- Commit or push only when the user asks.

## Commits

Use conventional commits: `<type>(<scope>): <subject>`. The types are `feat`, `fix`, `docs`,
`style`, `refactor`, `test`, `chore` (routine work and dependencies) and `ci`. The scope is
optional, for example `api`, `db`, `workers` or `ai`.

- The subject uses the imperative mood, lowercase, no period and at most 50 characters.
- Add a body only when the subject cannot carry the context. Separate it with one blank line.
- Wrap body lines at 72 characters. The body explains what changed and why.
- Bullet points use a hyphen and one space. Wrapped lines use a hanging indent.
- Write the body in ASD-STE100 (`core.md` §6).
- Commit messages carry no tool attribution or co-author trailers.

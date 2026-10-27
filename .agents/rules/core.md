# Core agent rules

## 1. Surface tradeoffs, do not guess

- State your assumptions. If a request has more than one meaning, show the options.
- If a simpler approach exists, say so.
- Explore the repository before you ask. Ask when the intent or a consequential choice is not
  in the code.

## 2. Simplicity first

Write the minimum code that solves the problem. Add no features that nobody asked for, no
abstraction for single-use code, no configuration that nobody needs and no error handling for
impossible cases. Add a package only when the standard library or a small function cannot do
the work. This template keeps few dependencies on purpose.

## 3. Surgical changes

Change only what the task needs. Do not reformat or refactor adjacent code that works. If you
see unrelated dead code, mention it. Remove the imports, variables and functions that your
change made unused. Every changed line must trace to the request.

## 4. Verifiable goals

Turn each task into a check. "Add validation" becomes "tests for invalid input pass". "Fix the
bug" becomes "a test that reproduces the bug passes". For multi-step work, state the plan and
the check for each step before you start.

## 5. Run the checks before you call it done

`just ci` runs `ruff format --check`, `ruff check`, `pyright`, `complexipy` and `pytest`. Run it
after each finished unit of work: a feature slice, before a commit and before a PR.

- Pyright covers `tests/` too. The complexity check covers `tests/` and `alembic/`.
- Never make a check pass by silencing it. A `# type: ignore`, a deleted assertion or a narrowed
  test hides the defect. When a suppression is the correct fix, give the reason on the same line.
- Report what actually ran. If you skipped a check or a check failed, say so with the output.

## 6. Code comments in ASD-STE100

Write code comments, commit messages and PR text in ASD-STE100 Simplified Technical English:

- Write a comment only for a constraint that the code cannot show.
- Write one idea per sentence. Use the active voice and simple verb forms.
- Use plain words and one term for each concept.
- Keep a comment to one or two lines.

## 7. Current external docs

When correctness depends on an external API that the codebase does not show (a new library, a
fast-moving SDK, version-specific behavior, a cloud contract), read the current upstream docs.
Do not rely on memory. Idioms that the codebase already uses need no lookup.

## 8. Documentation readiness

Before a PR, update the docs in the same branch when a change affects the API contract, the
configuration, the local setup, the deployment or the agent guidance. The targets are
`README.md`, `.env.example`, `AGENTS.md` and `.agents/rules/`. If no docs change is necessary,
say why in the PR.

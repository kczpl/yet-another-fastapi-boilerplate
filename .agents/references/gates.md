# Project gates

A gate is a check of one project convention. Its finding names the fix. An agent forgets a rule
in a long text, but a gate stops the same mistake each time. When an agent or a reviewer makes
the same correction twice, turn the correction into a gate.

## When to write a gate

Write a gate when all of these are true:

- The same mistake came back: in a review, in a bug or in an agent session.
- A script can decide the rule without judgment: a path, an import, a call, an AST pattern or
  a registry entry.
- The rule gives no false findings on the current code. Fix the old offenders in the same PR.

Keep a rule as text in `.agents/rules/` when it needs judgment, for example a name or a design
choice.

## The gates

| Gate | Checks | Exceptions |
|---|---|---|
| Ruff TID251 (`banned-api` in `pyproject.toml`) | Each wrapped API stays behind its wrapper: `SessionLocal`, the loggers, the Bedrock model and provider, the Celery task decorator. | `per-file-ignores` of the wrapper module, `tests/` and `scripts/` |
| Ruff TID252 | No relative imports, so the import direction test sees each import. | none |
| `tests/architecture/test_import_direction.py` | `app/core` and `app/utils` import no upper layer. Shared services and integrations import no feature. In a feature, imports go down: routes, dependencies, services, repository, models. | none |
| `tests/architecture/test_transaction_ownership.py` | Repositories never commit. | none |
| `tests/architecture/test_enqueue_convention.py` | Only the async `enqueue_*` helpers publish tasks. Workers import no feature at module level. | none |
| `tests/architecture/test_log_fields.py` | No personal data or secrets in the fields of `log.*` and `bind_context` calls. | none |
| `tests/architecture/test_model_conventions.py` | The model conventions of the database rule. | none |
| `tests/architecture/test_route_inventory.py` | Each route authenticates or has its reason in `PUBLIC_ROUTES`. | `PUBLIC_ROUTES` |
| `tests/core/test_error_registry.py` | Each raised error key is in `ERRORS`. | none |
| `tests/migrations/test_heads.py` | The migration history has one head. | none |
| complexipy (`just complexity`) | Cognitive complexity 10 per function. | none |

## Where the gates run

- `just gates` runs the strict ruff pass and the gate tests in about 1 s, without a database.
  Run it after each edit.
- `just ci` and CI run all gates. `just test` runs the gate tests with the other tests.

## Rules for each gate

- **The finding names the fix.** Name the helper, the file or the config entry. Example: "Use
  log from app.core.logger. The log field test reads only the log calls."
- **No comment switches a gate off.** `just gates` and CI run ruff with `--ignore-noqa` and the
  root config, so a `# noqa` or a nested `ruff.toml` has no effect. The tests read no comments.
  Put a real exception in the gate config, with a comment that gives the reason.
- **A gate has a self-test.** Write a case that must fail and a case that must pass. Remove the
  guard once and see the self-test fail.
- **A gate is fast.** It reads the source or the metadata, never the database.
- **Old offenders get a fix in the same PR.** The template has no baseline. A project that adds
  a gate late can list the old offenders in the test. Make the test fail also when a listed
  offender is clean, so that the list only gets shorter.
- **A gate change needs a reason.** When a commit adds an exception, removes a ban or raises a
  limit, its body says why.

## Add a gate

| Convention | Place |
|---|---|
| A library or a module has one wrapper. | An entry in `[tool.ruff.lint.flake8-tidy-imports.banned-api]` of `pyproject.toml`. The wrapper module gets a `per-file-ignores` entry. |
| A layer must not import another layer. | `FORBIDDEN_IMPORTS` or `FEATURE_FORBIDDEN` in `tests/architecture/test_import_direction.py`. |
| Another pattern in one file. | A test in `tests/architecture/`. Shared helpers are in `tests/architecture/source.py`. |
| A contract of the whole app. | A test that reads a registry: the route table, `ERRORS` or `Base.metadata`. |

Then do these steps:

1. Write the self-test cases.
2. Write the check and its message.
3. Run `just gates`. Fix each old offender.
4. Add one line that names the gate to the rule of the layer in `.agents/rules/`.
5. Run `just ci`.

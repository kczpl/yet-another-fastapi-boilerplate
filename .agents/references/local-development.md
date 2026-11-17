# Local development for agents

Read this guide before you start the app, call its API or run the tests. Run all commands
from the repository root. The `just` recipes ask for no input, and each one stops on its own.

## Set up the checkout

Run `just setup` first in each new checkout and each new git worktree, also when `.env`
exists. Run it again after a pull that changes the dependencies or `.env.example`.

- It installs all modules (`uv sync --locked --all-extras`) and creates `.env` from
  `.env.example`.
- It gives the checkout a slot N. The slot sets `COMPOSE_PROJECT_NAME` and adds N×10 to each
  port: API 8000, PostgreSQL 5432, test PostgreSQL 5433, Redis 6379.
- A new slot is free in the other worktrees and on the host. Another project on the machine
  can hold a port, so do not assume port 8000. Read the ports with `just urls`.
- A `.env` copied from another worktree carries its slot. `just setup` moves the copy to a new
  slot; the main checkout keeps its slot.
- Do not edit `SLOT`, `COMPOSE_PROJECT_NAME`, the ports or the localhost ports in
  `DATABASE_URL` and `REDIS_URL` by hand. `just setup` owns them.

`just up` and `just test` stop when another checkout uses the same slot. Run `just setup`,
then the command again.

## Run the stack

| Command | Result |
|---|---|
| `just up` | Builds and starts api, migrate and postgres in the background. Waits until they are healthy. Prints the URLs. |
| `COMPOSE_PROFILES=workers just up` | Also starts redis, workers and cron. |
| `just urls` | Prints the API, PostgreSQL and Redis addresses of this checkout. |
| `just ps` | Shows the state of the containers. |
| `just logs api` | Prints the last 200 log lines of a service and stops. Add `-f` only to follow them. |
| `just seed` | Loads three demo items into an empty database. Safe to run again. |
| `just down` | Stops all services of this checkout, also the test database and the workers. Keeps the data. |

The api container reloads on a change in `app/`. The workers do not reload: run
`docker compose restart workers` after a change. The migrate service applies the migrations
before the API starts. After you add a migration to a running stack, run `just migrate`.

## Call the API

The example routes are public. Read the port from `just urls`:

```bash
curl -s "http://localhost:$API_PORT/api/v1/items"
curl -s -X POST "http://localhost:$API_PORT/api/v1/items" -H 'content-type: application/json' -d '{"name": "Test"}'
```

`just` loads `.env`, but your shell does not. Read `API_PORT` from `.env` or `just urls` first.

## Run the checks

- `just test` starts the test database of this checkout and runs pytest. Give pytest
  arguments after it: `just test tests/features/items -q`.
- `just ci` runs lint, types, complexity and the tests. Run it before a commit.
- `just agents-check` checks only the agent guidance.

## Remove a worktree

`git worktree remove` does not stop the containers. Before you remove a worktree, run
`just down -v` in it. This deletes the volumes of that worktree only.

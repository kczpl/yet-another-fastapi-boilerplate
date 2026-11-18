# Deployment

Operating details of the API image. The local stack is in
[local development](../.agents/references/local-development.md), the workers in
[the workers reference](../.agents/references/workers.md).

## Image

The Dockerfile has two stages. The build stage installs the locked runtime packages with uv.
The final image gets only the virtual environment, `app/` and `alembic/`: no uv, no tests and
no development tools. It runs as a non-root user. `APP_EXTRA` (`workers` or `ai`) selects an
optional extra at build time.

The image does not migrate on startup. Compose runs one migration job before the API and the
workers. In another deployment, run `alembic -c alembic/alembic.ini upgrade head` once before
you start the replicas. Read the zero-downtime table in
[the database rule](../.agents/rules/backend/database.md) before a migration that removes or
renames.

## Probes

| Path | Checks | Use |
|---|---|---|
| `/up` | The process answers. No database call. | Liveness: restart the container on failure. |
| `/ready` | `SELECT 1` on the database. 503 when it fails. | Readiness: send no requests on failure. |

Do not use `/ready` for a restart check: a database outage then restarts each process. Both
probes skip the request log and the rate limit. A failed readiness check logs
`readiness_check_failed`.

## Shutdown

On SIGTERM, Uvicorn stops new connections and waits for the open requests. After 25 s
(`--timeout-graceful-shutdown`), it cancels them, then the lifespan closes the database pool.
Set the stop timeout of the platform above 25 s. Kubernetes and ECS wait 30 s by default;
`docker stop` waits only 10 s (`docker stop -t 30`). The workers have their own grace period
(`WORKER_STOP_GRACE_PERIOD`).

## Proxy and client IP

The middleware reads the client IP from the ASGI scope. Uvicorn takes it from
`X-Forwarded-For` only for proxies in `FORWARDED_ALLOW_IPS` (default: loopback). Behind a
proxy, set `FORWARDED_ALLOW_IPS` to the proxy addresses or network. If you do not, all clients
share the proxy IP: one rate-limit count and one block decision for everybody. Never set
`FORWARDED_ALLOW_IPS=*` when clients can reach Uvicorn directly, because they can then forge
their IP.

## Security middleware

Small ASGI middleware classes in `app/core/security.py` replace a security package:

| Setting or limit | Behavior |
|---|---|
| Request body: 10 MiB | Checks `Content-Length` and the bytes read, also for chunked bodies. 400 or 413. |
| `RATE_LIMIT_PER_MINUTE` (default 1000, `0` disables) | Fixed window per client IP and API process. 429 with `Retry-After`. The probes are exempt. |
| `BLOCKED_IPS` (JSON list of addresses or CIDRs) | 403 for HTTP, close code 1008 for WebSocket. |
| Security headers | HSTS, `nosniff`, `X-Frame-Options: DENY`, referrer, cross-origin and permissions policies on each response. |
| Request log | One `http_request` event with the status, the duration and `X-Request-ID`. |

The rate limit lives in process memory. N API processes allow N times the limit, and a
restart clears the counts. Put strict, shared or per-route limits, WAF rules and ingress
body/time limits at the reverse proxy or load balancer. The headers have no CSP, because a
CSP blocks the CDN assets of `/docs`. Add one when the API serves no HTML.

## Access

The example routes are public. Add authentication for your product: identity and access checks
in dependencies, business invariants in services. See
[authentication and tenancy](../.agents/references/auth-and-tenancy.md). CORS defaults to no
origins; list the deployed frontend origins explicitly. Docs and OpenAPI are off outside
development (`SHOW_DOCS` overrides).

## AWS credentials

The AI extra uses the standard AWS SDK chain: `AWS_PROFILE`, the standard credential
variables (also session tokens) or an IAM role. For Docker, give the container the
credentials with the mechanism of your deployment. Model clients start on first use, after
the worker fork, so the API import needs no AWS credentials.

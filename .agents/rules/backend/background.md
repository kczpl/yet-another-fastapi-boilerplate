---
paths:
  - "app/workers/**/*.py"
  - "app/features/**/services/**/*.py"
---

# Optional workers

Install `workers` or `ai` with uv. Docker services use the workers profile. Celery uses Redis,
JSON serialization, ignored results, late ACKs, rejection on worker loss and prefetch=1.
Queue constants live in `workers/queues.py`: default for short work, heavy for longer work.
Both queues are declared durable; unrouted tasks go to default and unknown queues are rejected.
A single worker consuming both queues does not isolate latency; use separate consumers when needed.

Tasks in `registry.py` are thin wrappers around `run_service()`. Import service classes inside
task bodies to avoid import cycles and parent-process client initialization. Feature code uses
typed helpers in `workers/enqueue.py`. Celery publishing is synchronous; don't block async routes.

## Lifecycle

Each prefork child owns one persistent asyncio.Runner. Init replaces the inherited SQLAlchemy
pool with `dispose(close=False)`; shutdown disposes the child pool and closes the runner.
Copy contextvars for each runner call. Task prerun clears/binds task context. `run_service()`
opens one session and commits on success or rolls back on failure. Never share that session
between concurrent coroutines. Build network/model clients lazily after fork.

## Retries and delivery

`max_retries` is only a limit; it doesn't enable retries. Use `autoretry_for` with specific
transient exceptions or explicit retry calls, bounded backoff and jitter. Business failures
normally propagate. Set a soft timeout below each task's hard timeout.
Ordinary failures/timeouts are acknowledged, preventing infinite redelivery of failing tasks.
Producer connection/publish retries are finite; worker connections retry indefinitely.
Connection loss cancels running unacknowledged tasks; cancellation cannot undo external effects.

The Redis visibility timeout must exceed every task's hard limit plus any ETA/countdown.
Validation compares it to the global limit only; review decorator overrides as well.
Whole-worker loss may wait for visibility timeout before redelivery. Avoid long ETA tasks.
Compose runs workers directly with an 11-minute shutdown grace period; keep it above task limits.
Restart workers to load code changes.

Late ACKs mean possible redelivery. The summary example skips already-completed results on
sequential redelivery, but concurrent tasks or a crash after an external call can repeat cost.
Do not call that exactly-once delivery. Use vendor idempotency keys and task-specific locking
or an outbox when required. A Redis marker written after sending does not close the crash window.

Beat has an example daily cleanup and per-queue heartbeat tasks. Keep one beat scheduler per
deployment. Sentry monitors these only when its DSN is configured. Tasks do not persist results;
add a result backend only when a workflow needs it.
Compose persists beat's schedule and syncs after each published task; it does not guarantee
catch-up of missed schedules or atomicity between schedule state and task publication.

Redis uses a volume, AOF with appendfsync always and noeviction. This prioritizes persistence
over throughput but does not provide high availability or protect against storage loss.
Convert existing RDB-only data to AOF online before restarting with the new configuration;
see README and the linked Redis persistence documentation.

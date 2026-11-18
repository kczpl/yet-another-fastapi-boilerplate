---
paths:
  - "app/workers/**/*.py"
---

# Optional workers

Install `workers` or `ai` with uv. Docker services use the workers profile. Celery uses Redis,
JSON serialization, ignored results, late ACKs, rejection on worker loss and prefetch=1.
Queue constants live in `workers/queues.py`: default for short work, heavy for longer work.
Both queues are declared durable; unrouted tasks go to default and unknown queues are rejected.
A single worker consuming both queues does not isolate latency; use separate consumers when needed.

Tasks in `registry.py` are thin wrappers around `run_service()`. Declare them with
`@celery_task(...)`, not with a raw `@celery.task`: the helper gives them the `BaseTask` type.
Import service classes inside task bodies to avoid import cycles and parent-process client
initialization.

Feature code awaits the async `enqueue_*` helpers of `workers/enqueue.py` after the commit.
A Celery publish blocks, so the helpers publish in their own thread pool. Tests reject
`.delay()` and `.apply_async()` outside `app/workers/`.
Task arguments are JSON values. The enqueue helper sends `str(item_id)`, and the task parses it
with `UUID(item_id)`. Services take typed values and return a TypedDict.

A message can still be lost. Before you add a task, decide what finds its lost work: a beat
task, a new request from the client, or nothing when the loss does no harm.

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

Late ACKs mean possible redelivery. The summary example skips already-completed results on
sequential redelivery, but concurrent tasks or a crash after an external call can repeat cost.
Do not call that exactly-once delivery. Use vendor idempotency keys and task-specific locking
or an outbox when required. A Redis marker written after sending does not close the crash window.
Idempotency converges on entity state, a unique constraint or a row lock. Do not deduplicate on
the Celery task_id: a retry reuses it. Never wait for the result of another task in a task; use
one task or a chain.

Beat runs the example daily cleanup and one heartbeat per queue. Keep one beat scheduler per
deployment. Beat entries use `crontab`, not `timedelta`: Sentry Crons reads cron expressions.
Tasks do not store results; add a result backend only when a workflow reads them.

Read the [workers reference](../../references/workers.md) before you add a recovery task or
change time limits, the visibility timeout, Redis persistence, beat persistence or the worker
settings of Compose.

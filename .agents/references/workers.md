# Workers: broker, limits and beat

Operating details of the optional Celery workers. The rules are in
[background.md](../rules/backend/background.md).

## Time limits and the visibility timeout

The Redis visibility timeout (`BROKER_VISIBILITY_TIMEOUT`, default 3600 s) must exceed every
task's hard limit plus any ETA or countdown. Startup validates it against the global
`TASK_TIME_LIMIT` (600 s) only. Check the limits in the task decorators yourself.

- After the loss of a whole worker, redelivery can wait until the visibility timeout ends.
  Avoid long ETA reservations in Redis.
- Compose runs the workers directly, so they receive SIGTERM. `WORKER_STOP_GRACE_PERIOD`
  (default 11 minutes) must stay above the longest hard limit.
- Restart the workers to load code changes (`docker compose restart workers`).

## Redis persistence

Compose runs Redis 8 with a volume, AOF, `appendfsync always` and `noeviction`. This prefers
persistence over throughput. It gives no high availability and no protection against the loss
of the disk or the node. Persistent messages do not give exactly-once execution.

- Redis 8 reads the data files of older versions. An older Redis cannot always read the files
  that Redis 8 wrote. Back up an existing volume before the upgrade.
- An existing RDB-only volume: back it up, enable AOF online (`CONFIG SET appendonly yes`) and
  wait for the AOF rewrite to finish. Only then restart with this Compose configuration. A
  restart with AOF enabled before the conversion can lose the data.
- See [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

## Beat

Compose keeps the beat schedule in the `celery_beat_data` volume and syncs it after each
published task. Beat is not a durable job ledger. It does not catch up missed runs, and the
schedule state and the publish are not atomic. Sentry monitors the beat tasks only when
`SENTRY_DSN` is set.

## Lost work

Late ACKs and `task_reject_on_worker_lost` redeliver a task after a crash. A message can still
be lost, for example when Redis loses data. Decide for each task what finds its lost work:

- A cron runs again at the next interval.
- The client can request the work again. The summary example uses this.
- When a lost task loses data, add a beat task that recovers it. It selects the rows in a
  pending state that are older than the longest delivery time and enqueues them again. It
  must be idempotent, like every task.

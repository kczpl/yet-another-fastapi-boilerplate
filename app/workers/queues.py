# Queues are split by runtime characteristic, not importance:
#   default — <10s, user-blocking, fast crons (emails, notifications, dispatch)
#   heavy   — >30s I/O bound (syncs, file processing, batch jobs, LLM/agent runs)
# Never hardcode queue strings in task decorators — import these constants.
QUEUE_DEFAULT = "default"
QUEUE_HEAVY = "heavy"

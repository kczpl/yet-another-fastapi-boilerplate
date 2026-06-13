from app.workers.registry import summarize_item_task

# Public API to enqueue tasks from application code. Feature services import these
# helpers — never call task.delay() / task.apply_async() directly from feature code.
# When you add a task, add a typed enqueue_<task_name> helper here.


def enqueue_summarize_item(item_id: str) -> None:
    summarize_item_task.delay(item_id)  # type: ignore[attr-defined]

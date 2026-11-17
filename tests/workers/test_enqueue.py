import pytest

pytest.importorskip("celery")

import threading
from uuid import uuid7

import structlog

from app.core.logger import bind_context, clear_context
from app.workers.enqueue import enqueue_summarize_item


async def test_enqueue_publishes_in_a_publisher_thread_with_the_caller_context(mock_celery):
    # A publish on the event loop thread stops every request while the broker hangs.
    seen = []
    mock_celery.side_effect = lambda *args, **kwargs: seen.append(
        (threading.current_thread().name, structlog.contextvars.get_contextvars().get("request_id"))
    )
    item_id = uuid7()
    bind_context(request_id="req-1")
    try:
        await enqueue_summarize_item(item_id)
    finally:
        clear_context()

    mock_celery.assert_called_once_with((str(item_id),), {})
    thread_name, request_id = seen[0]
    assert thread_name.startswith("celery-publish")
    assert request_id == "req-1"

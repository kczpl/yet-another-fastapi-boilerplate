import pytest

pytest.importorskip("celery")

from celery.exceptions import QueueNotFound

from app.workers.celery import celery
from app.workers.queues import QUEUE_DEFAULT


def test_unrouted_task_is_published_to_a_consumed_queue():
    # Real Kombu serialization/routing through an in-memory broker; no worker or Redis.
    with celery.connection_for_write("memory://") as connection:
        with connection.Producer() as producer:
            celery.send_task("tasks.heartbeat_default", producer=producer)
        with connection.SimpleQueue(QUEUE_DEFAULT) as queue:
            message = queue.get(block=False)
            try:
                assert message.headers["task"] == "tasks.heartbeat_default"
                assert message.properties["delivery_mode"] == 2
                assert message.content_type == "application/json"
            finally:
                message.ack()


def test_misspelled_queue_is_rejected_before_publishing():
    with pytest.raises(QueueNotFound):
        celery.amqp.router.route({"queue": "heavi"}, "tasks.summarize_item")

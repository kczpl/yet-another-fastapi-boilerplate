import pytest

pytest.importorskip("celery")

from app.workers.celery import celery
from app.workers.registry import TASKS_WITHOUT_RECOVERY


def _app_tasks() -> dict:
    celery.loader.import_default_modules()
    return {name: task for name, task in celery.tasks.items() if not name.startswith("celery.")}


def test_each_task_names_a_scheduled_recovery_or_a_reason():
    # Late ACKs and one Redis broker can lose a message; a beat task must find the lost work.
    scheduled = {entry["task"] for entry in celery.conf.beat_schedule.values()}
    offenders = []
    for name, task in _app_tasks().items():
        recovered_by = getattr(task, "recovered_by", "<not set>")
        if recovered_by is None and name not in TASKS_WITHOUT_RECOVERY:
            offenders.append(f"{name}: recovered_by=None without a reason in TASKS_WITHOUT_RECOVERY")
        elif recovered_by is not None and recovered_by not in scheduled:
            offenders.append(f"{name}: recovered_by={recovered_by!r} is not a beat task")
    assert offenders == []


def test_recovery_reasons_name_registered_tasks():
    assert set(TASKS_WITHOUT_RECOVERY) - set(_app_tasks()) == set()

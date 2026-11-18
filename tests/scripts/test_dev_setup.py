import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import dev_setup

GIT = shutil.which("git") or "git"


def _git(*args: str) -> None:
    subprocess.run([GIT, *args], check=True, capture_output=True)  # noqa: S603 — fixed git command, temporary directory


def test_choose_slot_skips_taken_slots_and_busy_ports():
    busy = {8010}  # slot 1 API port, held by another project

    assert dev_setup.choose_slot({0}, lambda port: port not in busy) == 2


@pytest.mark.parametrize(
    ("current", "others", "expected"),
    [
        ("main", {"feature": 1}, True),
        ("main", {"feature": 0}, True),
        ("feature", {"main": 0}, False),
        ("feature", {"main": 1}, True),
    ],
    ids=["unique", "main_keeps_shared", "copy_moves", "linked_unique"],
)
def test_keeps_slot(current: str, others: dict[str, int], expected: bool):
    main = Path("/repo/main")
    paths = {"main": main, "feature": Path("/repo/feature")}
    owners = {paths[name]: slot for name, slot in others.items()}

    assert dev_setup.keeps_slot(paths[current], 0, owners, main) is expected


def test_slot_values_move_local_urls_to_the_slot_ports():
    env = {
        "DATABASE_URL": "postgresql://app:app@localhost:5432/app",
        "REDIS_URL": "redis://localhost:6379/0",
    }

    values = dev_setup.slot_values(env, Path("/work/My Project"), 2)

    assert values["COMPOSE_PROJECT_NAME"] == "my-project-slot2"
    assert values["DATABASE_URL"] == "postgresql://app:app@localhost:5452/app"
    assert values["REDIS_URL"] == "redis://localhost:6399/0"
    assert values["POSTGRES_TEST_PORT"] == "5453"


def test_slot_values_keep_a_remote_database_host():
    values = dev_setup.slot_values({"DATABASE_URL": "postgresql://app:app@db.internal:5432/app"}, Path("/w/app"), 1)

    assert values["DATABASE_URL"] == "postgresql://app:app@db.internal:5432/app"


def test_write_env_replaces_keys_in_place_and_keeps_other_lines(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("# comment\nSLOT=0\nLOG_LEVEL=INFO\n")

    dev_setup.write_env(env, {"SLOT": "3", "API_PORT": "8030"})

    assert env.read_text() == "# comment\nSLOT=3\nLOG_LEVEL=INFO\nAPI_PORT=8030\n"


def _main_checkout(root: Path) -> Path:
    main = root / "main"
    main.mkdir()
    _git("-C", str(main), "init", "-q")
    (main / ".env.example").write_text("DATABASE_URL=postgresql://app:app@localhost:5432/app\n")
    _git("-C", str(main), "add", ".env.example")
    _git("-C", str(main), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
    return main.resolve()


def test_new_checkout_skips_a_slot_whose_ports_another_project_holds(tmp_path: Path):
    main = _main_checkout(tmp_path)

    first = dev_setup.setup(main, is_free=lambda port: port != 5433)
    again = dev_setup.setup(main, is_free=lambda port: False)

    assert first.startswith("Slot 1:")
    assert again.startswith("Slot 1:")


def test_worktree_with_a_copied_env_moves_to_a_new_slot(tmp_path: Path):
    main = _main_checkout(tmp_path)
    feature = tmp_path / "feature"
    _git("-C", str(main), "worktree", "add", "-q", str(feature))
    dev_setup.setup(main, is_free=lambda port: True)
    shutil.copy(main / ".env", feature / ".env")

    assert dev_setup.check(feature.resolve()) is not None
    assert dev_setup.setup(feature.resolve(), is_free=lambda port: True).startswith("Slot 1:")
    assert dev_setup.check(feature.resolve()) is None
    assert dev_setup.check(main) is None
    assert "DATABASE_URL=postgresql://app:app@localhost:5442/app" in (feature / ".env").read_text()

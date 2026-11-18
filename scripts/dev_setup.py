import argparse
import fcntl
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

# Gives each checkout (also each git worktree) its own slot: a Compose project name and host
# ports. Parallel agents in worktrees then do not share containers, ports or a test database.
# `--check` changes nothing. It fails when another checkout of the repository holds the same slot.
ROOT = Path(__file__).resolve().parents[1]
BASE_PORTS = {"API_PORT": 8000, "POSTGRES_PORT": 5432, "POSTGRES_TEST_PORT": 5433, "REDIS_PORT": 6379}
PORT_STEP = 10
MAX_SLOT = 50
LOCAL_URL = re.compile(r"(@|//)(localhost|127\.0\.0\.1):\d+")


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {key.strip(): value.strip() for key, value in pairs}


def slot_of(checkout: Path) -> int:
    # A checkout without a slot uses the default ports: slot 0.
    return int(read_env(checkout / ".env").get("SLOT", "0"))


def _git(root: Path, *args: str) -> str:
    command = ["git", "-C", str(root), *args]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout  # noqa: S603 — fixed git command


def checkouts(root: Path) -> list[Path]:
    # The first entry is the main worktree. A removed worktree directory holds no slot.
    listed = [line.removeprefix("worktree ") for line in _git(root, "worktree", "list", "--porcelain").splitlines()]
    paths = [Path(line).resolve() for line in listed if line.startswith("/")]
    return [path for path in paths if path.exists()]


@contextmanager
def setup_lock(root: Path) -> Iterator[None]:
    # Two parallel setups must not choose the same free slot.
    common_dir = root / _git(root, "rev-parse", "--git-common-dir").strip()
    with (common_dir / "dev-setup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def slot_ports(slot: int) -> dict[str, int]:
    return {name: port + slot * PORT_STEP for name, port in BASE_PORTS.items()}


def choose_slot(taken: set[int], is_free: Callable[[int], bool]) -> int:
    # Another project can hold a port too, so a new slot also needs free host ports.
    for slot in range(MAX_SLOT):
        if slot not in taken and all(is_free(port) for port in slot_ports(slot).values()):
            return slot
    raise SystemExit(f"No free slot below {MAX_SLOT}. Run `just down` in unused worktrees.")


def keeps_slot(current: Path, slot: int, others: dict[Path, int], main: Path) -> bool:
    # A copied .env carries the slot of its source. The main worktree keeps a shared slot.
    return current == main or slot not in others.values()


def project_name(main: Path, slot: int) -> str:
    base = re.sub(r"[^a-z0-9_-]", "-", main.name.lower()).strip("-") or "app"
    return base if slot == 0 else f"{base}-slot{slot}"


def slot_values(env: dict[str, str], main: Path, slot: int) -> dict[str, str]:
    ports = slot_ports(slot)
    values = {"SLOT": str(slot), "COMPOSE_PROJECT_NAME": project_name(main, slot)}
    values |= {name: str(port) for name, port in ports.items()}
    for name, port_name in (("DATABASE_URL", "POSTGRES_PORT"), ("REDIS_URL", "REDIS_PORT")):
        if name in env:
            values[name] = LOCAL_URL.sub(rf"\g<1>\g<2>:{ports[port_name]}", env[name])
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    # Replace the existing keys in place and append the others. Keep all other lines.
    lines = path.read_text().splitlines()
    seen = set()
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.startswith("#") and key in values:
            lines[index] = f"{key}={values[key]}"
            seen.add(key)
    lines += [f"{key}={value}" for key, value in values.items() if key not in seen]
    path.write_text("\n".join(lines) + "\n")


def other_slots(root: Path) -> tuple[Path, dict[Path, int]]:
    # A checkout that never ran setup holds no slot yet.
    all_checkouts = checkouts(root)
    assigned = [checkout for checkout in all_checkouts if checkout != root and "SLOT" in read_env(checkout / ".env")]
    return all_checkouts[0], {checkout: slot_of(checkout) for checkout in assigned}


def setup(root: Path, is_free: Callable[[int], bool] = port_is_free) -> str:
    env_path = root / ".env"
    if not env_path.exists():
        env_path.write_text((root / ".env.example").read_text())
    with setup_lock(root):
        main, others = other_slots(root)
        env = read_env(env_path)
        slot = slot_of(root)
        # Only a new assignment checks the ports: the containers of this checkout hold its own.
        if "SLOT" not in env or not keeps_slot(root, slot, others, main):
            slot = choose_slot(set(others.values()), is_free)
        write_env(env_path, slot_values(env, main, slot))
    ports = ", ".join(f"{name}={port}" for name, port in slot_ports(slot).items())
    return f"Slot {slot}: {ports}"


def check(root: Path) -> str | None:
    main, others = other_slots(root)
    slot = slot_of(root)
    if keeps_slot(root, slot, others, main):
        return None
    return f"Another checkout also uses slot {slot}. Run `just setup` in this checkout."


def main() -> int:
    parser = argparse.ArgumentParser(description="Give this checkout its own Compose slot.")
    parser.add_argument("--check", action="store_true", help="fail when another checkout uses the same slot")
    args = parser.parse_args()
    if args.check:
        problem = check(ROOT)
        if problem:
            sys.stderr.write(f"{problem}\n")
        return 1 if problem else 0
    sys.stdout.write(f"{setup(ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

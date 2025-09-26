#!/usr/bin/env python3

import subprocess
import sys
import os
from urllib.parse import quote
from dotenv import load_dotenv


def parse_postgres_url(url: str) -> dict:
    """Parse PostgreSQL URL and extract connection components."""
    # Remove the protocol prefix
    if url.startswith("postgresql://"):
        url = url[13:]
    elif url.startswith("postgres://"):
        url = url[11:]

    # Split by @ to separate user:password from host:port/database
    user_pass, host_db = url.split("@", 1)

    # Split user:password
    if ":" in user_pass:
        user, password = user_pass.split(":", 1)
    else:
        user = user_pass
        password = ""

    # Split host:port/database
    if "/" in host_db:
        host_port, database = host_db.split("/", 1)
    else:
        host_port = host_db
        database = "postgres"

    # Split host:port
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        try:
            port = int(port)
        except ValueError:
            port = 5432
    else:
        host = host_port
        port = 5432

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def run_pgq(postgres_url: str):
    """Run pgq command with parsed PostgreSQL connection details."""
    try:
        # parse the PostgreSQL URL
        conn_params = parse_postgres_url(postgres_url)

        # build the pgq command with URL-encoded password
        cmd = [
            "uv",
            "run",
            "pgq",
            "--pg-host",
            conn_params["host"],
            "--pg-port",
            str(conn_params["port"]),
            "--pg-user",
            conn_params["user"],
            "--pg-password",
            quote(conn_params["password"], safe=""),
            "--pg-database",
            conn_params["database"],
            "install",
        ]

        print(f"Running: {' '.join(cmd)}")

        # run the command
        subprocess.run(cmd, check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error running pgq: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    load_dotenv()
    postgres_url = os.getenv("DATABASE_URL")
    run_pgq(postgres_url)

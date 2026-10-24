"""The UnderCover database: SQLite, seeded from data/."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCHEMA = """
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS policies;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS plans;
DROP TABLE IF EXISTS handlers;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS steps;
DROP TABLE IF EXISTS payments;

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    policy_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    data TEXT NOT NULL,
    status TEXT NOT NULL,
    thread_id TEXT,
    decision TEXT,
    decided_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT
);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Return the database file: UNDERCOVER_DB if set, else undercover.db."""
    return Path(os.getenv("UNDERCOVER_DB", str(ROOT / "undercover.db")))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open the database, commit on success and roll back on error."""
    connection = sqlite3.connect(db_path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def load(name: str) -> Any:
    """Read one JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def insert(db: sqlite3.Connection, table: str, key: str, records: list[Any]) -> None:
    """Insert records into a table that stores each one as JSON under its key."""
    db.executemany(
        f"INSERT INTO {table} ({key}, data) VALUES (?, ?)",  # noqa: S608
        [(record[key], json.dumps(record)) for record in records],
    )


def seed(db: sqlite3.Connection) -> None:
    """Drop every table and load the business data from data/."""
    db.executescript(SCHEMA)
    plans = load("plans.json")
    company = load("company.json")
    insert(db, "plans", "plan", plans["plans"])
    insert(db, "policies", "policy_id", load("policies.json"))
    insert(db, "customers", "customer_id", load("customers.json"))
    insert(db, "handlers", "handler_id", load("handlers.json"))
    db.executemany(
        "INSERT INTO claims (claim_id, position, policy_id, customer_id, data, status)"
        " VALUES (?, ?, ?, ?, ?, 'waiting')",
        [
            (c["claim_id"], i, c["policy_id"], c["customer_id"], json.dumps(c))
            for i, c in enumerate(load("claims.json"))
        ],
    )
    settings = {
        "payout_approval_limit": company["payout_approval_limit"],
        "add_ons": plans["add_ons"],
        "deductible_applies_to": plans["deductible_applies_to"],
        "policy_wording": {
            "version": company["policy_wording_version"],
            "text": (DATA / "policy_wording.md").read_text(encoding="utf-8"),
        },
    }
    db.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [(key, json.dumps(value)) for key, value in settings.items()],
    )


def ensure_seeded() -> None:
    """Seed the database if it has no claims table yet."""
    with connect() as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'claims'"
        ).fetchone()
        if not exists:
            seed(db)


def setting(db: sqlite3.Connection, key: str) -> Any:
    """Read one setting."""
    return json.loads(
        db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()[0]
    )


if __name__ == "__main__":
    with connect() as connection:
        seed(connection)
    print(f"Reset {db_path()} with the claims queue from data/")

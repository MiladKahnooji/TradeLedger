"""Small SQLite persistence layer for TradeLedger."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    broker TEXT NOT NULL,
    initial_balance NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    analysis_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    weekly TEXT NOT NULL DEFAULT 'Not Assessed',
    daily TEXT NOT NULL DEFAULT 'Not Assessed',
    h4 TEXT NOT NULL DEFAULT 'Not Assessed',
    h1 TEXT NOT NULL DEFAULT 'Not Assessed',
    m15 TEXT NOT NULL DEFAULT 'Not Assessed',
    status TEXT NOT NULL DEFAULT 'Draft',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_at TEXT,
    exit_at TEXT,
    entry_price NUMERIC NOT NULL,
    exit_price NUMERIC,
    stop_loss NUMERIC,
    take_profit NUMERIC,
    lot_size NUMERIC NOT NULL,
    net_pnl NUMERIC,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trade_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    category TEXT NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str | Path = "tradeledger.db") -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: str | Path = "tradeledger.db") -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        columns = connection.execute("PRAGMA table_info(trades)").fetchall()
        net_pnl = next(column for column in columns if column["name"] == "net_pnl")
        if net_pnl["notnull"]:
            connection.executescript(
                """
                ALTER TABLE trades RENAME TO trades_legacy;
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
                    analysis_id INTEGER REFERENCES analyses(id) ON DELETE SET NULL,
                    instrument TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_at TEXT,
                    exit_at TEXT,
                    entry_price NUMERIC NOT NULL,
                    exit_price NUMERIC,
                    stop_loss NUMERIC,
                    take_profit NUMERIC,
                    lot_size NUMERIC NOT NULL,
                    net_pnl NUMERIC,
                    notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Open',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO trades SELECT id, account_id, analysis_id, instrument, direction,
                    entry_at, exit_at, entry_price, exit_price, stop_loss, take_profit,
                    lot_size, CASE WHEN status = 'Open' THEN NULL ELSE net_pnl END, notes, status, created_at FROM trades_legacy;
                DROP TABLE trades_legacy;
                """
            )


def fetch_all(
    path: str | Path, query: str, parameters: tuple[Any, ...] = ()
) -> list[sqlite3.Row]:
    with connect(path) as connection:
        return connection.execute(query, parameters).fetchall()


def fetch_one(
    path: str | Path, query: str, parameters: tuple[Any, ...] = ()
) -> sqlite3.Row | None:
    with connect(path) as connection:
        return connection.execute(query, parameters).fetchone()


def execute(path: str | Path, query: str, parameters: tuple[Any, ...] = ()) -> int:
    with connect(path) as connection:
        cursor = connection.execute(query, parameters)
        return int(cursor.lastrowid or 0)


def delete_trade(path: str | Path, trade_id: int) -> None:
    with connect(path) as connection:
        connection.execute("DELETE FROM trades WHERE id = ?", (trade_id,))


def fetch_trade_screenshots(path: str | Path, trade_id: int) -> list[sqlite3.Row]:
    return fetch_all(
        path,
        "SELECT * FROM trade_screenshots WHERE trade_id = ? ORDER BY id",
        (trade_id,),
    )

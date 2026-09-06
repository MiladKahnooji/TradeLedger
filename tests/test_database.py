from app import add_demo_data, demo_exists
from tradeledger.database import connect, delete_trade, execute, initialize


def test_database_initializes_and_links_trade(tmp_path):
    path = tmp_path / "test.db"
    initialize(path)
    account_id = execute(
        path,
        "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
        ("Main", "Demo", "1000.00"),
    )
    trade_id = execute(
        path,
        "INSERT INTO trades(account_id, instrument, direction, entry_price, lot_size) VALUES (?, ?, ?, ?, ?)",
        (account_id, "XAUUSD", "Long", "2000", "0.1"),
    )
    with connect(path) as connection:
        row = connection.execute(
            "SELECT instrument, exit_at, net_pnl FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
    assert row["instrument"] == "XAUUSD"
    assert row["exit_at"] is None
    assert row["net_pnl"] is None
    delete_trade(path, trade_id)


def test_trade_deletion_preserves_account_and_analysis(tmp_path):
    path = tmp_path / "relations.db"
    initialize(path)
    account_id = execute(
        path,
        "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
        ("Main", "Demo", "1000"),
    )
    analysis_id = execute(
        path,
        "INSERT INTO analyses(instrument, direction, analysis_at) VALUES (?, ?, ?)",
        ("XAUUSD", "Long", "2026-01-01T10:00"),
    )
    trade_id = execute(
        path,
        "INSERT INTO trades(account_id, analysis_id, instrument, direction, entry_price, lot_size) VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, analysis_id, "XAUUSD", "Long", "2000", "0.1"),
    )
    delete_trade(path, trade_id)
    with connect(path) as connection:
        assert connection.execute(
            "SELECT id FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        assert connection.execute(
            "SELECT id FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()


def test_demo_insertion_is_not_duplicate(tmp_path, monkeypatch):
    path = tmp_path / "demo.db"
    monkeypatch.setattr("app.DB_PATH", path)
    initialize(path)
    assert demo_exists() is False
    assert add_demo_data() is True
    assert add_demo_data() is False
    with connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 2


def test_existing_non_null_pnl_schema_is_upgraded_without_losing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    with connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT NOT NULL, broker TEXT NOT NULL, initial_balance NUMERIC NOT NULL, currency TEXT NOT NULL DEFAULT 'USD', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE analyses (id INTEGER PRIMARY KEY, instrument TEXT NOT NULL, direction TEXT NOT NULL, analysis_at TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', weekly TEXT NOT NULL DEFAULT 'Not Assessed', daily TEXT NOT NULL DEFAULT 'Not Assessed', h4 TEXT NOT NULL DEFAULT 'Not Assessed', h1 TEXT NOT NULL DEFAULT 'Not Assessed', m15 TEXT NOT NULL DEFAULT 'Not Assessed', status TEXT NOT NULL DEFAULT 'Draft', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE trades (id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, analysis_id INTEGER, instrument TEXT NOT NULL, direction TEXT NOT NULL, entry_at TEXT, exit_at TEXT, entry_price NUMERIC NOT NULL, exit_price NUMERIC, stop_loss NUMERIC, take_profit NUMERIC, lot_size NUMERIC NOT NULL, net_pnl NUMERIC NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Open', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO accounts(id, name, broker, initial_balance) VALUES (1, 'Existing', 'Broker', 1000);
            INSERT INTO trades(id, account_id, instrument, direction, entry_price, lot_size, net_pnl) VALUES (1, 1, 'EURUSD', 'Long', 1.1, 1, 0);
            """
        )
    initialize(path)
    with connect(path) as connection:
        columns = {
            row["name"]: row["notnull"]
            for row in connection.execute("PRAGMA table_info(trades)")
        }
        assert columns["net_pnl"] == 0
        assert (
            connection.execute("SELECT instrument FROM trades WHERE id = 1").fetchone()[
                0
            ]
            == "EURUSD"
        )


def test_screenshot_table_is_idempotent_and_existing_records_remain(tmp_path):
    path = tmp_path / "existing.db"
    initialize(path)
    account_id = execute(
        path,
        "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
        ("Main", "Broker", "1000"),
    )
    execute(
        path,
        "INSERT INTO trades(account_id, instrument, direction, entry_price, lot_size) VALUES (?, ?, ?, ?, ?)",
        (account_id, "EURUSD", "Long", "1.1", "1"),
    )
    initialize(path)
    with connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name = 'trade_screenshots'"
            ).fetchone()[0]
            == 1
        )

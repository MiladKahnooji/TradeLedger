from __future__ import annotations

import io
import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from app import gallery_metadata, screenshot_counter
from tradeledger.database import connect, execute, fetch_trade_screenshots, initialize
from tradeledger.screenshots import (
    MAX_FILE_SIZE,
    MAX_SCREENSHOTS_PER_TRADE,
    delete_screenshot,
    delete_trade_screenshots,
    resolve_owned_path,
    save_screenshot,
    validate_image,
)


class Upload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def image_upload(image_format: str, name: str | None = None) -> Upload:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format=image_format)
    suffix = image_format.lower().replace("jpeg", "jpg")
    return Upload(name or f"shot.{suffix}", buffer.getvalue())


def trade_fixture(tmp_path: Path) -> tuple[Path, Path, int]:
    db_path = tmp_path / "journal.db"
    root = tmp_path / "screenshots"
    initialize(db_path)
    account_id = execute(
        db_path,
        "INSERT INTO accounts(name, broker, initial_balance) VALUES (?, ?, ?)",
        ("Main", "Broker", "1000"),
    )
    trade_id = execute(
        db_path,
        "INSERT INTO trades(account_id, instrument, direction, entry_price, lot_size) VALUES (?, ?, ?, ?, ?)",
        (account_id, "EURUSD", "Long", "1.1", "1"),
    )
    return db_path, root, trade_id


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_supported_images_are_verified(tmp_path, image_format):
    db_path, root, trade_id = trade_fixture(tmp_path)
    screenshot_id = save_screenshot(
        db_path, root, trade_id, image_upload(image_format), "Before Entry", "setup"
    )
    row = fetch_trade_screenshots(db_path, trade_id)[0]
    assert row["id"] == screenshot_id
    assert row["relative_path"] == f"{trade_id}/{Path(row['relative_path']).name}"
    assert not Path(row["relative_path"]).is_absolute()
    assert (root / row["relative_path"]).is_file()


def test_malformed_unsupported_and_oversized_images_are_rejected():
    with pytest.raises(ValueError, match="valid supported image"):
        validate_image(Upload("bad.png", b"not an image"))
    with pytest.raises(ValueError, match="supported"):
        validate_image(image_upload("BMP", "shot.bmp"))
    with pytest.raises(ValueError, match="10 MB"):
        validate_image(Upload("large.png", b"x" * (MAX_FILE_SIZE + 1)))


def test_limit_unique_names_and_persistence_across_restarts(tmp_path):
    db_path, root, trade_id = trade_fixture(tmp_path)
    first = save_screenshot(
        db_path,
        root,
        trade_id,
        image_upload("PNG", "same.png"),
        "Before Entry",
        "setup",
    )
    second = save_screenshot(
        db_path,
        root,
        trade_id,
        image_upload("PNG", "same.png"),
        "After Exit",
        "result",
    )
    rows = fetch_trade_screenshots(db_path, trade_id)
    assert first != second
    assert rows[0]["relative_path"] != rows[1]["relative_path"]
    assert [(row["category"], row["caption"]) for row in rows] == [
        ("Before Entry", "setup"),
        ("After Exit", "result"),
    ]
    initialize(db_path)
    assert len(fetch_trade_screenshots(db_path, trade_id)) == 2
    for _ in range(MAX_SCREENSHOTS_PER_TRADE - 2):
        save_screenshot(db_path, root, trade_id, image_upload("PNG"), "Other")
    with pytest.raises(ValueError, match="at most 10"):
        save_screenshot(db_path, root, trade_id, image_upload("PNG"), "Other")


def test_path_traversal_is_rejected():
    with pytest.raises(ValueError, match="outside|relative"):
        resolve_owned_path("/tmp/screenshots", "../outside.png")
    with pytest.raises(ValueError, match="relative"):
        resolve_owned_path("/tmp/screenshots", "/tmp/outside.png")
    with pytest.raises(ValueError, match="outside|relative"):
        resolve_owned_path("/tmp/screenshots", r"..\outside.png")


def test_screenshot_counter_accounts_for_existing_and_selected_files():
    assert (
        screenshot_counter(0, 2)
        == "2 screenshots selected · 8 of 10 screenshot slots remaining"
    )
    assert (
        screenshot_counter(3, 2)
        == "2 screenshots selected · 5 of 10 screenshot slots remaining"
    )
    assert (
        screenshot_counter(9, 1)
        == "1 screenshot selected · 0 of 10 screenshot slots remaining"
    )
    assert (
        screenshot_counter(10, 1)
        == "1 screenshot selected · 0 of 10 screenshot slots remaining"
    )


def test_gallery_metadata_order_omits_empty_caption():
    row = {
        "category": "Before Entry",
        "caption": "",
        "original_filename": "chart.png",
        "created_at": "2026-09-06T10:00",
    }
    assert gallery_metadata(row) == [
        ("Category", "Before Entry"),
        ("Filename", "chart.png"),
        ("Added", "2026-09-06 10:00 UTC"),
    ]


def test_metadata_failure_cleans_new_file(tmp_path):
    db_path, root, trade_id = trade_fixture(tmp_path)
    with connect(db_path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_screenshot_insert BEFORE INSERT ON trade_screenshots BEGIN SELECT RAISE(ABORT, 'test failure'); END"
        )
    with pytest.raises(sqlite3.Error):
        save_screenshot(db_path, root, trade_id, image_upload("PNG"), "Other")
    assert list(root.rglob("*")) == []


def test_individual_delete_and_missing_file_cleanup(tmp_path):
    db_path, root, trade_id = trade_fixture(tmp_path)
    screenshot_id = save_screenshot(
        db_path, root, trade_id, image_upload("PNG"), "Other"
    )
    row = fetch_trade_screenshots(db_path, trade_id)[0]
    (root / row["relative_path"]).unlink()
    assert delete_screenshot(db_path, root, screenshot_id) is True
    assert fetch_trade_screenshots(db_path, trade_id) == []
    assert delete_screenshot(db_path, root, screenshot_id) is False


def test_trade_delete_removes_only_owned_screenshots(tmp_path):
    db_path, root, trade_id = trade_fixture(tmp_path)
    with connect(db_path) as connection:
        account_id = connection.execute("SELECT id FROM accounts LIMIT 1").fetchone()[0]
    other_trade = execute(
        db_path,
        "INSERT INTO trades(account_id, instrument, direction, entry_price, lot_size) VALUES (?, ?, ?, ?, ?)",
        (account_id, "XAUUSD", "Short", "2000", "0.1"),
    )
    save_screenshot(db_path, root, trade_id, image_upload("PNG"), "Before Entry")
    save_screenshot(db_path, root, other_trade, image_upload("PNG"), "Other")
    owned = root / fetch_trade_screenshots(db_path, trade_id)[0]["relative_path"]
    sibling = root / fetch_trade_screenshots(db_path, other_trade)[0]["relative_path"]
    delete_trade_screenshots(db_path, root, trade_id)
    assert not owned.exists()
    assert sibling.exists()
    assert fetch_trade_screenshots(db_path, other_trade)
